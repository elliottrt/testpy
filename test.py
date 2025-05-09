#! python3

# Ordered by length.
import os
import sys
import json
import argparse
import subprocess
from dataclasses import dataclass
from typing import cast, Optional, Union, Any, Generator


__version_info__ = (1, 0, 6)
__version__ = '%d.%d.%d' % __version_info__

'''
TODO: actual docstrings for all functions, class methods included
TODO: better fail messages - just printing TestCaseOutput is hard to understand
TODO: see if print_error is really needed
TODO: option to time test cases and overall
'''


# Dataclass containing test result information.
@dataclass
class TestCaseOutput:
    stdout: str
    stderr: str
    returncode: int
    command: Optional[str]

    def __eq__(self, value: Any) -> bool:
        if isinstance(value, TestCaseOutput):
            return self.stdout == value.stdout \
                and self.stderr == value.stderr \
                and self.returncode == value.returncode
        else:
            return False

    def to_json(self) -> dict[str, Union[str, int]]:
        return {
            'stdout': self.stdout,
            'stderr': self.stderr,
            'returncode': self.returncode
        }

    def __str__(self) -> str:
        return f'TestCaseOutput(stdout=\'{self.stdout}\', ' + \
            f'stderr=\'{self.stderr}\', returncode={self.returncode})'


# Exception information about executed test cases.
class TestCaseException:
    def __init__(self, command: str, exception: Exception):
        self.command = command
        self.exception = exception

    # Returns the description of what caused this exception.
    # return: str -- the description of what caused this exception.
    def error_string(self) -> str:
        return f'Exception executing \'{self.command}\': {self.exception}'


# Dataclass containing information about test results.
@dataclass
class TestResult:
    test_path: str
    record_path: str
    expected_output: Union[TestCaseOutput, str]
    actual_output: Optional[Union[TestCaseOutput, TestCaseException]]

    # Returns whether the test has passed or failed.
    # return: bool -- true if this test passed, false otherwise.
    def passed(self) -> bool:
        return not self.skipped() and \
            self.expected_output == self.actual_output

    # Returns whether this Test was skipped.
    # return: bool -- true if this test was skipped, false otherwise.
    def skipped(self) -> bool:
        return isinstance(self.expected_output, str)


# Class that contains and formats program invocations.
class ProgramTemplate:
    # Constructor for ProgramTemplate.
    # program_command: str -- command template for test execution.
    # symbol: str -- symbol to replace with the test case path.
    # return: None.
    def __init__(self, program_command: str, symbol: str):
        self.program_template = program_command
        self.symbol = symbol

        # if the program template does not contain the symbol,
        # we assume that we should put it at the end.
        if self.symbol not in self.program_template:
            self.program_template = self.program_template + ' ' + self.symbol

    # Formats the test case execution command.
    # test_path: str -- path to the test case.
    # return: str -- command to execute to run the test case.
    def format(self, test_path: str) -> str:
        return self.program_template.replace(self.symbol, test_path)


# Contains a list of all arguments used by this program.
@dataclass
class TestArguments(argparse.Namespace):
    test_ext: str
    record_ext: str
    test_case: str
    update: bool
    program_template: str
    symbol: str
    create_empty: bool
    no_recursion: bool
    fail_only: bool


# Prints an error message.
# error_message: str -- the error message to print.
# return: None.
def print_error(error_message: str) -> None:
    print(f'ERROR: {error_message}')


# Returns whether the file pointed to by the path exists and is a file.
# path: str -- the path to check.
# return: bool -- true if the path is a valid file, false otherwise.
def is_valid_file(path: str) -> bool:
    return os.path.exists(path) and os.path.isfile(path)


# Returns whether the file pointed to by the path exists and is a directory.
# path: str -- the path to check.
# return: bool -- true if the path is a valid directory, false otherwise.
def is_valid_dir(path: str) -> bool:
    return os.path.exists(path) and os.path.isdir(path)


# Returns a list of paths representing all test cases in the
#       test directory matching an optional file extension.
# test_path: str -- the path to a single test or a directory
#       containing test cases.
# record_file_extension: str -- the file extension of record files.
# test_file_extension: Optional[str] -- an optional file extension to filter.
# return: Optional[list[str]] -- a list of test file paths,
#       or None if test_path is not a valid file/directory.
def get_tests(
        test_path: str,
        record_file_extension: str,
        test_file_extension: Optional[str],
        recursive: bool) -> Optional[list[str]]:
    # make sure the test directory is valid
    if is_valid_dir(test_path):
        # get all items and include full paths from where this is executed

        try:
            matches = [
                os.path.join(test_path, fn)
                for fn in os.listdir(test_path)
            ]
        except PermissionError as e:
            print_error(f'cannot access {test_path}: {e.strerror}')
            exit(1)

        if recursive:
            child_dirs = [
                dp for dp in matches
                if is_valid_dir(dp)
            ]
            child_dir_matches = [
                get_tests(
                    dp,
                    record_file_extension,
                    test_file_extension,
                    recursive
                ) for dp in child_dirs
            ]
            child_dir_matches_flat = [
                child for children in child_dir_matches
                if children is not None
                for child in children
            ]
        else:
            child_dir_matches_flat = []

        # make sure these are all files that exist, and are not record files
        matches = [
            fp for fp in matches
            if is_valid_file(fp) and not fp.endswith(record_file_extension)
        ]

        # if the user specified a test file extension, filter for that
        if test_file_extension is not None:
            matches = [
                fp for fp in matches
                if fp.endswith(test_file_extension)
            ]

        # sort them so tests are run in alphabetical order
        return sorted(matches + child_dir_matches_flat)
    # if the directory wasn't valid, return None
    elif is_valid_file(test_path):
        return [test_path]
    else:
        return None


# Returns the corresponding record path of a test file.
# test_path: str -- the path to the test file.
# record_file_extension: str -- the file extension of record files.
# return: str -- the record path corresponding to the test case path.
def record_path_of(test_path: str, record_file_extension: str) -> str:
    # drop the extension from the test path and try to find a matching record
    (base_path, _) = os.path.splitext(test_path)
    # make sure the file extension has a dot in front of it
    return base_path + \
        ('' if record_file_extension.startswith('.') else '.') + \
        record_file_extension


# Returns the bytes of a test case record file.
# If the case cannot be found, returns None.
# record_path: str -- the file path of the test case record.
# return: Union[TestCaseOutput, str] -- the expected test case output
#       or error message if the record file path is invalid.
def read_record_of(record_path: str) -> Union[TestCaseOutput, str]:
    # return the bytes if the file exists
    if is_valid_file(record_path):
        try:
            with open(record_path, 'r') as record:
                record_json: dict[str, Union[str, int]] = json.load(record)

                stdout = record_json['stdout']
                stderr = record_json['stderr']
                returncode = record_json['returncode']

                if isinstance(stdout, str) and \
                    isinstance(stderr, str) and \
                        isinstance(returncode, int):
                    return TestCaseOutput(stdout, stderr, returncode, None)
        except PermissionError as e:
            print_error(f'cannot access {record_path}: {e.strerror}')
            exit(1)
        except Exception:
            pass

        # error if the if statement fails or the json data is invalid
        return 'BAD RECORD'
    else:
        return 'NO RECORD'


# Writes bytes to a test case record file.
# record_path: str -- the file path of the test case record.
# output: TestCaseOutput -- the test case output to write.
# return: None.
def write_record_of(record_path: str, output: TestCaseOutput) -> None:
    with open(record_path, 'w') as record:
        json.dump(
            obj=output.to_json(),
            fp=record,
            indent=4,
            separators=(', ', ': ')
        )


# Runs the program that is being tested with the test case file.
# template: ProgramTemplate -- the program template to execute.
# test_path: str -- the path to the test case file.
# timeout: Optional[int] -- the number of milliseconds to wait before test
#        timeout failure may be None, in which case there is no timeout
# return: Union[TestCaseOutput, TestCaseException] -- the expected test case
#       output or an exception if one occurred.
def run_and_capture(
        template: ProgramTemplate,
        test_path: str,
        timeout: Optional[int]) -> Union[TestCaseOutput, TestCaseException]:
    # format the test case command and split it for subprocess
    test_command = template.format(test_path)

    try:
        process = subprocess.run(
            test_command,
            capture_output=True,
            shell=True,
            timeout=timeout / 1000 if timeout is not None else None
        )
    except subprocess.TimeoutExpired:
        return TestCaseException(test_command, Exception('timed out'))
    except Exception as e:
        return TestCaseException(test_command, e)

    return TestCaseOutput(
        # convert the bytes to a utf-8 string for storage
        str(process.stdout, encoding='utf-8'),
        str(process.stderr, encoding='utf-8'),
        process.returncode,
        test_command
    )


# Record test results to test against in future runs.
# template: ProgramTemplate -- the program template to execute.
# test_paths: list[str] -- a list of test case file paths.
# record_file_extension: str -- the file extension of record files.
# create_empty: bool -- if set, creates empty test case files.
# echo: bool -- whether to echo the commands that are executed.
# timeout: Optional[int] -- the number of milliseconds to wait before test
#        timeout failure may be None, in which case there is no timeout
# return: None.
def update_tests(
        template: ProgramTemplate,
        test_paths: list[str],
        record_file_extension: str,
        create_empty: bool,
        echo: bool,
        timeout: Optional[int]) -> None:

    for test_path in test_paths:
        # find the record it belongs to
        record_path = record_path_of(test_path, record_file_extension)
        if create_empty:
            # write an empty test case if requested
            write_record_of(record_path, TestCaseOutput('', '', 0, None))
        else:
            # get the output from the test case
            actual_output = run_and_capture(template, test_path, timeout)
            # update the record with the new output
            if isinstance(actual_output, TestCaseOutput):

                if echo:
                    print(f'CMD: {actual_output.command}')

                write_record_of(record_path, actual_output)
            else:
                print_error(actual_output.error_string())


# Run each test, compare it to the corresponding record file,
# and return the results of each test.
# template: ProgramTemplate -- the program template to execute.
# test_paths: list[str] -- a list of test case file paths.
# record_file_extension: str -- the file extension of record files.
# timeout: Optional[int] -- the number of milliseconds to wait before test
#        timeout failure may be None, in which case there is no timeout
# return: list[TestResult] -- return the TestResult for each test.
def run_tests(
        template: ProgramTemplate,
        test_paths: list[str],
        record_file_extension: str,
        timeout: int) -> Generator[TestResult, None, None]:

    for test_path in test_paths:
        # find the record path and read the expected output
        record_path = record_path_of(test_path, record_file_extension)
        expected_output = read_record_of(record_path)
        yield TestResult(
            test_path, record_path, expected_output,
            # if expected output is an error message, skip the test
            # and don't run the test case
            None if isinstance(expected_output, str)
            else run_and_capture(template, test_path, timeout)
        )


# Print test failure information.
# result: TestResult -- the result information for the failed test.
# return: None.
def print_failure(result: TestResult) -> None:
    if isinstance(result.actual_output, TestCaseOutput):
        # print out expected and actual for failed test cases
        print(f'    EXPECTED: {result.expected_output}')
        print(f'    ACTUAL:   {result.actual_output}')
    elif isinstance(result.actual_output, TestCaseException):
        print(f'    ERROR: {result.actual_output.error_string()}')


# Print test case results.
# results: Generator[TestResult, None, None] -- Generator of results for tests.
# fail_only: bool -- if true, only display information about failing tests.
# color_text: bool -- whether to display colored text in results
# echo: bool -- whether to echo the command used to test
# return: int -- the exit code of the program.
def display_results(
        results: Generator[TestResult, None, None],
        fail_only: bool,
        use_color: bool,
        echo: bool) -> int:

    tests_passed = 0
    total_tests = 0

    for result in results:

        if echo and isinstance(result.actual_output, TestCaseOutput) and \
                not (fail_only and result.passed()):
            print(f'CMD: {result.actual_output.command}')

        test_string = f'TEST: \'{result.test_path}\'... '
        # if result was skipped, ignore this case
        if result.skipped():
            if not fail_only:
                if use_color:
                    print(f'{test_string}\033[38;5;{8}mSKIPPED,',
                          f'{result.expected_output}\033[0m')
                else:
                    print(f'{test_string}SKIPPED, {result.expected_output}')
        # if the test pass, print that and increase the number of
        # successful tests and total tests
        elif result.passed():
            if not fail_only:
                if use_color:
                    print(f'{test_string}\033[38;5;{2}mOK\033[0m')
                else:
                    print(f'{test_string}OK')
            tests_passed += 1
            total_tests += 1
        # if the test failed, print the difference between expected and actual
        else:
            if use_color:
                print(f'{test_string}\033[38;5;{9}mFAIL\033[0m')
            else:
                print(f'{test_string}FAIL')
            print_failure(result)
            total_tests += 1

    print(f'{tests_passed}/{total_tests} tests passed')

    # return success if all tests passed, else failure
    return 0 if tests_passed == total_tests else 1


# Returns whether two file extensions are equal.
# ext_a: str -- the first file extension.
# ext_b: str -- the second file extension.
# return: bool -- true if the file extensions are equal, false otherwise.
def extensions_equal(ext_a: str, ext_b: str) -> bool:
    # make sure '.<ext>' and '<ext>' are considered equal
    temp_ext_a = ext_a[1:] if ext_a.startswith('.') else ext_a
    temp_ext_b = ext_b[1:] if ext_b.startswith('.') else ext_b
    return temp_ext_a == temp_ext_b


# Create the ArgumentParser for this program.
# return: ArgumentParser -- the argument parser for this program.
def create_argparser() -> argparse.ArgumentParser:

    PROGRAM_TEMPLATE_EXPLANATION = (
        'The program_template argument describes what command to run for '
        'each test. This may be a single executable or a more complex command.'
        'For a simple executable, the test file path is appended to the end of'
        ' the command, like \'<executable> <test file path>\'.'
        'If the desired command is more complex, quotes ("", \'\') should be '
        'used around the command and a symbol may be use which is replaced '
        'with the name of the test case file for each test case. This can be '
        'set with the \'-s\' and \'--symbol\' arguments.'
        'For example, \'python @ 1 2 3\' will run each test case with \'@\' '
        'replaced with the test case file path.'
    )

    # create argparser
    args = argparse.ArgumentParser(
        prog='test.py',
        description='A basic test runner utility.',
        epilog=PROGRAM_TEMPLATE_EXPLANATION,
        argument_default=None
    )

    # Positional, Required Arguments
    args.add_argument(
        'program_template',
        help='program template to run'
    )
    args.add_argument(
        'test_case', nargs='+',
        help='one or more test cases or directories containing test cases'
    )

    # Options
    args.add_argument(
        '-u', '--update', action='store_true',
        help='updates test cases if set'
    )
    args.add_argument(
        '-t', '--test-ext', default=None, type=str,
        help='file extension of test cases,\
              ignored if the test case is a single file'
    )
    args.add_argument(
        '-r', '--record-ext', default='rec', type=str,
        help='file extension of record cases, the default is \'rec\''
    )
    args.add_argument(
        '-s', '--symbol', default='@', type=str,
        help='symbol to replace with test case in command template,\
              the default is \'@\''
    )
    args.add_argument(
        '-c', '--create-empty', action='store_true',
        help='create empty record files for manual test case writing'
    )
    args.add_argument(
        '-n', '--no-recursion', action='store_true',
        help='disable recursive search for test cases'
    )
    args.add_argument(
        '-f', '--fail-only', action='store_true',
        help='only display information about failing tests'
    )
    args.add_argument(
        '-o', '--no-color', action='store_true',
        help='do not print colored text when displaying test case results'
    )
    args.add_argument(
        '-e', '--echo', action='store_true',
        help='echo commands that are used to test the test cases'
    )
    args.add_argument(
        '-v', '--version', action='version',
        version='%(prog)s ' + __version__
    )
    args.add_argument(
        '-T', '--timeout', default=None, type=int,
        help='number of milliseconds to wait until test failure due to timeout'
    )

    return args


# Main driver function, parses command line arguments and
# either runs or updates tests.
# argv: Optional[list[str]] -- command line arguments.
# return: int -- the exit code of the program.
def do_tests(argv: Optional[list[str]] = None) -> int:
    # create the ArgumentParser
    argparser = create_argparser()

    # parse the args and cast for type checking
    settings = cast(TestArguments, argparser.parse_args(argv))

    # make sure the test file extension and the record file extension differ
    if settings.test_ext is not None and \
            extensions_equal(settings.test_ext, settings.record_ext):
        argparser.error('record extension and test extension may not be equal')

    if settings.timeout is not None and settings.timeout < 1:
        argparser.error(
            f'invalid timeout value {settings.timeout}ms, must be at least 1'
        )

    program_template = ProgramTemplate(
        settings.program_template,
        settings.symbol
    )

    tests_to_run = {case: get_tests(
        case,
        settings.record_ext,
        settings.test_ext,
        recursive=not settings.no_recursion
    ) for case in settings.test_case}

    # if one or more test paths weren't accessible, print error(s)
    invalid_paths = [k for k, v in tests_to_run.items() if v is None]
    if len(invalid_paths) > 0:
        for invalid_path in invalid_paths:
            print_error(
                f'unable to access test case file/dir \'{invalid_path}\''
            )
        return 1

    flattened_test_list = [
        test_case for path, test_list in tests_to_run.items()
        if test_list is not None
        for test_case in test_list
    ]

    # if we need to update the tests, do that
    if settings.update or settings.create_empty:
        update_tests(
            program_template,
            flattened_test_list,
            settings.record_ext,
            settings.create_empty,
            settings.echo,
            settings.timeout
        )

        return 0
    # otherwise run the tests and return the exitcode display_results returns
    else:
        test_results = run_tests(
            program_template,
            flattened_test_list,
            settings.record_ext,
            settings.timeout
        )

        return display_results(
            test_results,
            settings.fail_only,
            not settings.no_color and sys.stdout.isatty(),
            settings.echo
        )


if __name__ == '__main__':
    exit(do_tests())
