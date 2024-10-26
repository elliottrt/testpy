
# Ordered by length.
import os
import sys
import json
import argparse
import subprocess
from typing import cast, Optional, Union, Any, Generator
from dataclasses import dataclass


TEST_CASE_OUTPUT_STDOUT = 'stdout'
TEST_CASE_OUTPUT_STDERR = 'stderr'
TEST_CASE_OUTPUT_RETURNCODE = 'returncode'


# TODO: doc comments for all class functions
# TODO: put everything into one class that takes all of the options so this can be more easily used from other files
# TODO: convert things that return lists to generators with yield

# Dataclass containing test result information.
@dataclass
class TestCaseOutput:
	stdout: str
	stderr: str
	returncode: int

	def __eq__(self, value: Any) -> bool:
		if isinstance(value, TestCaseOutput):
			return self.stdout == value.stdout \
				and self.stderr == value.stderr \
				and self.returncode == value.returncode
		else:
			return False

	def to_json(self) -> dict[str, Union[str, int]]:
		return {
			TEST_CASE_OUTPUT_STDOUT: self.stdout,
			TEST_CASE_OUTPUT_STDERR: self.stderr,
			TEST_CASE_OUTPUT_RETURNCODE: self.returncode
		}

	# TODO: to string or __str__ or __repr__


# Exception information about executed test cases.
class TestCaseException:
	def __init__(self, command: str, exception: Exception):
		self.command = command
		self.exception = exception

	# Returns the description of what caused this exception.
	# return: str -- the description of what caused this exception.
	def error_string(self) -> str:
		return f'Exception executing command "{self.command}": {self.exception}'


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
		return not self.skipped() and self.expected_output == self.actual_output

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


# Prints an error message.
# error_message: str -- the error message to print.
# return: None.
def print_error(error_message: str) -> None:
	print(f'error: {error_message}')


# Prints the usage of this test runner and an optional error message.
# this_name: str -- the name of this python file.
# error_message: Optional[str] -- an optional error message to print.
# return: None.
def print_usage(this_name: str, error_message: Optional[str] = None) -> None:
	print('Usage:')
	print(f'\t{this_name} <program name> <tests folder> [-ext <test file extension>] [-record]')

	# display the error message if there is one,
	# and separate it from the usage with a new line.
	if error_message is not None:
		print('')
		print_error(error_message)


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


# Returns a list of paths representing all test cases in the test directory matching an optional file extension.
# test_path: str -- the path to a single test or a directory containing test cases.
# record_file_extension: str -- the file extension of record files.
# test_file_extension: Optional[str] -- an optional file extension to filter by.
# return: Optional[list[str]] -- a list of test file paths, or None if test_path is not a valid file/directory.
def get_tests(test_path: str, record_file_extension: str, test_file_extension: Optional[str]) -> Optional[list[str]]:
	# make sure the test directory is valid
	if is_valid_dir(test_path):
		# get all the items, and include the full paths from where this is executed
		matches = [os.path.join(test_path, fn) for fn in os.listdir(test_path)]

		# make sure these are all files that exist, and are not record files
		matches = [fp for fp in matches if is_valid_file(fp) and not fp.endswith(record_file_extension)]

		# if the user specified a test file extension, filter for that
		if test_file_extension is not None:
			matches = [fp for fp in matches if fp.endswith(test_file_extension)]

		# sort them so tests are run in alphabetical order
		return sorted(matches)
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
	# drop the extension from the test path, and try to find a record path with that base
	(base_path, _) = os.path.splitext(test_path)
	# make sure the file extension has a dot in front of it
	return base_path + ('' if record_file_extension.startswith('.') else '.') + record_file_extension


# Returns the bytes of a test case record file.
# If the case cannot be found, returns None.
# record_path: str -- the file path of the test case record.
# return: Union[TestCaseOutput, str] -- the expected test case output, or error message if the record file path is invalid.
def read_record_of(record_path: str) -> Union[TestCaseOutput, str]:
	# return the bytes if the file exists
	if is_valid_file(record_path):
		with open(record_path, 'r') as record:
			try:
				record_json: dict[str, Union[str, int]] = json.load(record)

				stdout = record_json[TEST_CASE_OUTPUT_STDOUT]
				stderr = record_json[TEST_CASE_OUTPUT_STDERR]
				returncode = record_json[TEST_CASE_OUTPUT_RETURNCODE]

				if isinstance(stdout, str) and isinstance(stderr, str) and isinstance(returncode, int):
					return TestCaseOutput(stdout, stderr, returncode)
			except Exception:
				pass

			# error if the if statement fails or the json doesn't contain the right info
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
# test_case_path: str -- the path to the test case file.
# return: Union[TestCaseOutput, TestCaseException] -- the expected test case output or an exception if one occurred.
def run_and_capture(template: ProgramTemplate, test_path: str) -> Union[TestCaseOutput, TestCaseException]:
	# format the test case command and split it for subprocess
	test_command = template.format(test_path)

	try:
		process = subprocess.run(test_command.split(' '), capture_output=True)
	except Exception as excp:
		return TestCaseException(test_command, excp)

	return TestCaseOutput(
		# convert the bytes to a utf-8 string for storage
		str(process.stdout, encoding='utf-8'),
		str(process.stderr, encoding='utf-8'),
		process.returncode
	)


# Record test results to test against in future runs.
# template: ProgramTemplate -- the program template to execute.
# test_paths: list[str] -- a list of test case file paths.
# record_file_extension: str -- the file extension of record files.
# create_empty: bool -- if set, creates empty test case files for manual editing.
# return: None.
def update_tests(template: ProgramTemplate, test_paths: list[str], record_file_extension: str, create_empty: bool) -> None:
	for test_path in test_paths:
		# find the record it belongs to
		record_path = record_path_of(test_path, record_file_extension)
		if create_empty:
			# write an empty test case if requested
			write_record_of(record_path, TestCaseOutput('', '', 0))
		else:
			# get the output from the test case
			actual_output = run_and_capture(template, test_path)
			# update the record with the new output
			if isinstance(actual_output, TestCaseOutput):
				write_record_of(record_path, actual_output)
			else:
				print_error(actual_output.error_string())


# Run each test, compare it to the corresponding record file, and return the results of each test.
# template: ProgramTemplate -- the program template to execute.
# test_paths: list[str] -- a list of test case file paths.
# record_file_extension: str -- the file extension of record files.
# return: list[TestResult] -- return the TestResult for each test.
def run_tests(template: ProgramTemplate, test_paths: list[str], record_file_extension: str) -> Generator[TestResult]:
	for test_path in test_paths:
		# find the record path and read the expected output
		record_path = record_path_of(test_path, record_file_extension)
		expected_output = read_record_of(record_path)
		yield TestResult(
			test_path, record_path, expected_output,
			# if expected output is an error message, we skip the test and don't run the test case
			None if isinstance(expected_output, str) else run_and_capture(template, test_path)
		)


# Print test failure information.
# result: TestResult -- the result information for the failed test.
# return: None.
def print_failure(result: TestResult) -> None:
	# TODO: print out where specifically it failed, and
	# a comparison between the two things like "...[text]... vs ...[bird]..."

	# TODO: do we need to print out things that are equal?
	# if stdout, retcode are equal but stderr, differs,
	# should we only print stderr?

	if isinstance(result.actual_output, TestCaseOutput):
		# print out expected and actual for failed test cases
		print(f"    EXPECTED: {result.expected_output}")
		print(f"    ACTUAL:   {result.actual_output}")
	elif isinstance(result.actual_output, TestCaseException):
		print(f"    ERROR: {result.actual_output.error_string()}")


# Print test case results.
# results: list[TestResult] -- the list of results for each test.
# return: int -- the exit code of the program.
def display_results(results: Generator[TestResult]) -> int:
	tests_passed = 0
	total_tests = 0

	for result in results:
		print(f'TEST: \'{result.test_path}\'... ', end='')
		# if result was skipped, ignore this case and adjust total tests accordingly
		if result.skipped():
			print(f'\033[38;5;{8}mSKIPPED, {result.expected_output}\033[0m')
		# if the test pass, print that and increase the number of successful tests
		elif result.passed():
			# TODO: better way of printing colors
			print(f'\033[38;5;{2}mOK\033[0m')
			tests_passed += 1
			total_tests += 1
		# if the test failed, print the difference between expected and actual
		else:
			print(f'\033[38;5;{9}mFAIL\033[0m')
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
# this_name: str -- the name of this python file.
# return: ArgumentParser -- the argument parser for this program.
def create_argparser(this_name: str) -> argparse.ArgumentParser:

	PROGRAM_TEMPLATE_EXPLANATION = """
	The program_template argument describes what command to run for each test. This may be a single executable, or a more complex command.
	For a simple executable, the test file path is appended to the end of the command, like "<executable> <test file path>".
	If the desired command is more complex, quotes ("") should be used around the command and a symbol may be use which is replaced with
	the name of the test case file for each test case. This can be set with the '-s' and '--symbol' arguments. If not set, the default is used.
	For example, "python @ 1 2 3" will run each test case with '@' replaced with the test case file path.
	"""

	# create argparser
	args = argparse.ArgumentParser(
		prog=this_name,
		description='A basic test runner utility.',
		epilog=PROGRAM_TEMPLATE_EXPLANATION,
		argument_default=None
	)

	args.add_argument('program_template', help='program template to run')
	args.add_argument('test_case', help='test case or directory of test cases')

	args.add_argument('-u', '--update', action='store_true', help='updates test cases if set')
	args.add_argument('-e', '--test-ext', default=None, type=str, help='file extension of test cases. ignored if the test case is a single file')
	args.add_argument('-r', '--record-ext', default='rec', type=str, help='file extension of record cases, default=\'rec\'')
	args.add_argument('-s', '--symbol', default='@', type=str, help='symbol to replace with test case in command template, default=\'@\'')
	args.add_argument('-c', '--create-empty', action='store_true', help='create empty record files for manual test case writing')

	return args


# Main driver function, parses command line arguments and either runs or records tests.
# argv: list[str] -- command line arguments.
# return: int -- the exit code of the program.
def do_tests(argv: list[str]) -> int:
	# create the ArgumentParser
	argparser = create_argparser(argv[0])

	# for some reason, argparse assumes the first element isn't the program name
	settings = cast(TestArguments, argparser.parse_args(argv[1:]))

	# make sure the test file extension and the record file extension aren't equal
	if settings.test_ext is not None and extensions_equal(settings.test_ext, settings.record_ext):
		argparser.error('record extension and test extension may not be equal')

	# create program template and get all the tests to run
	program_template = ProgramTemplate(settings.program_template, settings.symbol)
	tests_to_run = get_tests(settings.test_case, settings.record_ext, settings.test_ext)

	# make sure the test directory exists
	if tests_to_run is not None:
		# if we need to update the tests, do that
		if settings.update or settings.create_empty:
			update_tests(program_template, tests_to_run, settings.record_ext, settings.create_empty)
			return 0
		# otherwise run the tests and return the exitcode display_results returns
		else:
			test_results = run_tests(program_template, tests_to_run, settings.record_ext)
			return display_results(test_results)

	# if the test directory didn't exist, print that error
	else:
		print_error(f'directory \'{settings.test_case}\' does not exist or is not a file or directory')
		return 1


# TODO: recursive test directory search for test cases
if __name__ == '__main__':
	sys.exit(do_tests(sys.argv))
