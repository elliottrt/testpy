
# Ordered by length.
import os
import sys
import argparse
import subprocess
from typing import *
from dataclasses import dataclass

# TODO: comment the processes for each function


# TODO: stderr and exit code information in the record
# Dataclass containing information about test results.
@dataclass
class TestResult:
	test_path: str
	record_path: str
	expected_output: bytes
	actual_output: bytes
	skipped: bool


	# Returns whether the test has passed or failed.
	# return: bool -- true if this test passed, false otherwise.
	def passed(self) -> bool:
		return self.expected_output == self.actual_output


# Class that contains and formats program invocations.
class ProgramTemplate:

	# Constructor for ProgramTemplate.
	# program_command: str -- command template for test execution.
	# symbol: str -- symbol to replace with the test case path.
	# return: None.
	def __init__(self, program_command: str, symbol: str):
		self.program_template = program_command
		self.symbol = symbol

		if self.symbol not in self.program_template:
			self.program_template = self.program_template + ' ' + self.symbol

	# Formats the test case execution command.
	# test_path: str -- path to the test case.
	# return: str -- command to execute to run the test case.
	def format(self, test_path: str) -> str:
		return self.program_template.replace(self.symbol, test_path)


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
# test_dir_path: str -- the path to the directory containing the test cases.
# record_file_extension: str -- the file extension of record files.
# test_file_extension: Optional[str] -- an optional file extension to filter by.
# return: Optional[list[str]] -- a list of test file paths, or None if test_dir_path is not a valid directory.
def get_tests(test_dir_path: str, record_file_extension: str, test_file_extension: Optional[str]) -> Optional[list[str]]:
	if is_valid_dir(test_dir_path):
		all_items = [os.path.join(test_dir_path, fn) for fn in os.listdir(test_dir_path)]
		matches = [fp for fp in all_items if is_valid_file(fp) and not fp.endswith(record_file_extension)]
		if test_file_extension is not None:
			matches = [fp for fp in matches if fp.endswith(test_file_extension)]

		matches.sort()
		return matches
	else:
		return None


# Returns the corresponding record path of a test file.
# test_case_path: str -- the path to the test file.
# record_file_extension: str -- the file extension of record files.
# return: str -- the record path corresponding to the test case path.
def record_path_of(test_case_path: str, record_file_extension: str) -> str:
	(base, _) = os.path.splitext(test_case_path)
	# make sure the file extension has a dot in front of it
	return base + ('' if record_file_extension.startswith('.') else '.') + record_file_extension



# Returns the bytes of a test case record file.
# If the case cannot be found, returns None.
# record_path: str -- the file path of the test case record.
# return: Optiona[bytes] -- the bytes of a test case record file, or None if the record file path is invalid.
def read_record_of(record_path: str) -> Optional[bytes]:
	if is_valid_file(record_path):
		with open(record_path, 'rb') as record:
			return record.read()
	else:
		return None


# Writes bytes to a test case record file.
# record_path: str -- the file path of the test case record.
# output_bytes: bytes -- the bytes to write.
# return: None.
def write_record_of(record_path: str, output_bytes: bytes) -> None:
	with open(record_path, 'wb') as record:
		record.write(output_bytes)


# Runs the program that is being tested with the test case file.
# program_path: str -- the path to the program to test.
# test_case_path: str -- the path to the test case file.
# return: bytes -- the stdout output of the test being run.
def run_and_capture(template: ProgramTemplate, test_path: str) -> bytes:
	# TODO: catch exceptions raised by this process
	test_command = template.format(test_path).split(' ')
	process = subprocess.run(test_command, capture_output=True)
	return process.stdout


# Record test results to test against in future runs.
# program_path: str -- the path to the program to test.
# test_paths: list[str] -- a list of test case file paths.
# record_file_extension: str -- the file extension of record files.
# return: None.
def update_tests(template: ProgramTemplate, test_paths: list[str], record_file_extension: str) -> None:
	for test_path in test_paths:
		actual = run_and_capture(template, test_path)
		record_path = record_path_of(test_path, record_file_extension)
		write_record_of(record_path, actual)


# Run each test, compare it to the corresponding record file, and return the results of each test.
# program_path: str -- the path to the program to test.
# test_paths: list[str] -- a list of test case file paths.
# record_file_extension: str -- the file extension of record files.
# return: list[TestResult] -- return the TestResult for each test.
def run_tests(template: ProgramTemplate, test_paths: list[str], record_file_extension: str) -> list[TestResult]:
	results = []
	for test_path in test_paths:
		record_path = record_path_of(test_path, record_file_extension)
		expected_output = read_record_of(record_path)
		if expected_output is None:
			results.append(TestResult(test_path, record_path, b'', b'', skipped=True))
		else:
			test_command = template.format(test_path)
			actual_output = run_and_capture(template, test_path)
			results.append(TestResult(test_path, record_path, expected_output, actual_output, skipped=False))
	return results


# Print test failure information.
# test_path: str -- the test case file path.
# expected_output: bytes -- the expected test output.
# actual_output: bytes -- the actual test output.
# return: None.
def print_failure(result: TestResult) -> None:
	print(f"    EXPECTED: {result.expected_output!r}")
	print(f"    ACTUAL: {result.actual_output!r}")


# Print test case results.
# results: list of tuples of (test_case_path, expected_output, actual_output).
# return: int -- the exit code of the program.
def display_results(results: list[TestResult]) -> int:
	tests_passed = 0
	total_tests = len(results)

	for result in results:
		print(f'TEST: \'{result.test_path}\'... ', end='')
		if result.skipped:
			print(f'\033[38;5;{8}m{'SKIPPED, NO RECORD'}\033[0m')
			total_tests -= 1
		elif result.passed():
			# TODO: better way of printing colors
			print(f'\033[38;5;{2}m{'OK'}\033[0m')
			tests_passed += 1
		else:
			print(f'\033[38;5;{9}m{'FAIL'}\033[0m')
			print_failure(result)

	print(f'{tests_passed}/{total_tests} tests passed')

	# return success if all tests passed, else failure
	return 0 if tests_passed == total_tests else 1


# Returns whether two file extensions are equal.
# ext_a: str -- the first file extension.
# ext_b: str -- the second file extension.
# return: bool -- true if the file extensions are equal, false otherwise.
def extensions_equal(ext_a: str, ext_b: str) -> bool:
	temp_ext_a = ext_a[1:] if ext_a.startswith('.') else ext_a
	temp_ext_b = ext_b[1:] if ext_b.startswith('.') else ext_b
	return temp_ext_a == temp_ext_b


# Main driver function, parses command line arguments and either runs or records tests.
# argv: list[str] -- command line arguments.
# return: int -- the exit code of the program.
def do_tests(argv: list[str]) -> int:

	PROGRAM_TEMPLATE_EXPLANATION = """
	The program_template argument describes what command to run for each test. This may be a single executable, or a more complex command.
	If the desired command is more complex, quotes ("") should be used around the command and a symbol may be use which is replaced with
	the name of the test case file for each test case. This can be set with the '-s' and '--symbol' arguments. If not set, the default is used.
	For example, "python @ 1 2 3" will run each test case with '@' replaced with the test case file path.
	"""

	args = argparse.ArgumentParser(
		prog=argv[0],
		description='A basic test runner utility.',
		epilog=PROGRAM_TEMPLATE_EXPLANATION,
		argument_default=None
	)

	args.add_argument('program_template', help='program template to run')
	args.add_argument('test_dir', help='directory containing test cases')

	args.add_argument('-u', '--update', action='store_true', help='updates test cases if set')
	args.add_argument('-e', '--test-ext', default=None, type=str, help='file extension of test cases')
	args.add_argument('-r', '--record-ext', default='rec', type=str, help='file extension of record cases, default=\'rec\'')
	args.add_argument('-s', '--symbol', default='@', type=str, help='symbol to replace with test case in command template, default=\'@\'')

	# for some reason, argparse assumes the first element isn't the program name
	settings = args.parse_args(argv[1:])

	if settings.test_ext is not None and extensions_equal(settings.test_ext, settings.record_ext):
		args.error('record extension and test extension may not be equal')

	exit_code = 0
	program_template = ProgramTemplate(settings.program_template, settings.symbol)
	tests_to_run = get_tests(settings.test_dir, settings.record_ext, settings.test_ext)
	if tests_to_run is not None:
		if settings.update:
			update_tests(program_template, tests_to_run, settings.record_ext)
		else:
			test_results = run_tests(program_template, tests_to_run, settings.record_ext)
			exit_code = display_results(test_results)
	else:
		print_error(f'directory \'{settings.test_dir}\' does not exist or is not a directory')
		exit_code = 1

	return exit_code


if __name__ == '__main__':
	sys.exit(do_tests(sys.argv))
