
import sys
import os
import subprocess
from typing import *


# TODO: comment the processes for each function
# TODO: comment return values

# Prints an error message.
# error_message: str -- the error message to print.
def print_error(error_message: str) -> None:
	print(f'error: {error_message}')


# Prints the usage of this test runner and an optional error message.
# this_name: str -- the name of this python file.
# error_message: Optional[str] -- an optional error message to print.
def print_usage(this_name: str, error_message: Optional[str] = None) -> None:
	print('Usage:')
	print(f'\t{this_name} <program name> <tests folder> [-ext <test file extension>] [-record]')

	if error_message is not None:
		print('')
		print_error(error_message)


# Returns whether the file pointed to by the path exists and is a file.
# path: str -- the path to check.
def is_valid_file(path: str) -> bool:
	return os.path.exists(path) and os.path.isfile(path)


# Returns whether the file pointed to by the path exists and is a directory.
# path: str -- the path to check.
def is_valid_dir(path: str) -> bool:
	return os.path.exists(path) and os.path.isdir(path)


# Returns a list of paths representing all test cases in the test directory matching an optional file extension.
# test_dir_path: str -- the path to the directory containing the test cases.
# record_file_extension: str -- the file extension of record files.
# test_file_extension: Optional[str] -- an optional file extension to filter by.
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
def record_path_of(test_case_path: str, record_file_extension: str) -> str:
	(base, _) = os.path.splitext(test_case_path)
	return base + record_file_extension


# Returns the bytes of a test case record file.
# If the case cannot be found, returns None.
# record_file_path: str -- the file path of the test case record.
def read_record_of(record_file_path: str) -> Optional[bytes]:
	if is_valid_file(record_file_path):
		with open(record_file_path, 'rb') as record:
			return record.read()
	else:
		return None


# Writes bytes to a test case record file.
# record_file_path: str -- the file path of the test case record.
# output_bytes: bytes -- the bytes to write.
def write_record_of(record_file_path: str, output_bytes: bytes) -> None:
	with open(record_file_path, 'wb') as record:
		record.write(output_bytes)


# TODO: this assumes that `prog file` is enough to run a test.
# change program_name in args to program_run_format with some special
# character to indicate where the filepath goes
# so something like: `./main % -run` would execute with % replaced by the test case name
# note: if the symbol does not exist, append filepath to the end

# Runs the program that is being tested with the test case file.
# program_path: str -- the path to the program to test.
# test_case_path: str -- the path to the test case file.
def run_and_capture(program_path: str, test_case_path: str) -> bytes:
	process = subprocess.run([program_path, test_case_path], capture_output=True)
	return process.stdout


# Record test results to test against in future runs.
# program_path: str -- the path to the program to test.
# test_paths: list[str] -- a list of test case file paths.
# record_file_extension: str -- the file extension of record files.
def record_tests(program_path: str, test_paths: list[str], record_file_extension: str) -> None:
	for test_path in test_paths:
		actual = run_and_capture(program_path, test_path)

		record_file_path = record_path_of(test_path, record_file_extension)

		write_record_of(record_file_path, actual)


# Run each test, compare it to the corresponding record file, and return the results of each test.
# program_path: str -- the path to the program to test.
# test_paths: list[str] -- a list of test case file paths.
# record_file_extension: str -- the file extension of record files.
def run_tests(program_path: str, test_paths: list[str], record_file_extension: str) -> list[tuple[str, bytes, bytes]]:
	results = []

	for test_path in test_paths:
		record_file_path = record_path_of(test_path, record_file_extension)
		expected = read_record_of(record_file_path)

		if expected is None:
			print(f'record {record_file_path} does not exist, skipping...')
		else:
			actual = run_and_capture(program_path, test_path)
			results.append((test_path, expected, actual))

	return results


# Returns whether a test has passed or failed.
# expected_output: bytes -- the expected test output.
# actual_output: bytes -- the actual test output.
def did_test_pass(expected_output: bytes, actual_output: bytes) -> bool:
	return expected_output == actual_output


# Print test failure information.
# test_path: str -- the test case file path.
# expected_output: bytes -- the expected test output.
# actual_output: bytes -- the actual test output.
def print_failure(expected_output: bytes, actual_output: bytes) -> None:
	print(f"    EXPECTED: {expected_output!r}")
	print(f"    ACTUAL: {actual_output!r}")

# TODO: use dataclass instead of tuple for results

# Print test case results.
# results: list of tuples of (test_case_path, expected_output, actual_output).
def display_results(results: list[tuple[str, bytes, bytes]]) -> int:
	tests_passed = 0

	for (test_path, expected, actual) in results:

		# TODO: print out full command used
		print(f'TEST: \'{test_path}\'... ', end='')
		if did_test_pass(expected, actual):
			# TODO: better way of printing colors
			print(f'\033[38;5;{2}m{'OK'}\033[0m')
			tests_passed += 1
		else:
			print(f'\033[38;5;{9}m{'FAIL'}\033[0m')
			print_failure(expected, actual)

	total_tests = len(results)
	print(f'{tests_passed}/{total_tests} tests passed')

	# return success if all tests passed, else failure
	return 0 if tests_passed == total_tests else 1

# TODO: seperate argument parsing into another function
# note: argparse?

# TODO: error if record file extension and case file extension are the same

# Main driver function, parses command line arguments and either runs or records tests.
# argv: list[str] -- command line arguments.
def do_tests(argv: list[str]) -> int:
	test_file_extension = None
	record_file_extension = ".rec"

	script_name, *argv = argv

	if len(argv) == 0:
		print_usage(script_name, 'missing program and test dir names')
		return 1;

	program_name, *argv = argv

	if len(argv) == 0:
		print_usage(script_name, 'missing test dir name')
		return 1;

	test_dir_name, *argv = argv

	# test_extensions are optional
	test_extension = None
	record = False

	if len(argv) != 0:
		option, *argv = argv
		if option == "-record":
			record = True
		if option == "-ext":
			if len(argv) > 0:
				test_extension, *argv = argv
			else:
				print_usage(script_name, 'encountered extension option without value')

	exit_code = 0

	tests_to_run = get_tests(test_dir_name, record_file_extension, test_file_extension)

	if tests_to_run is not None:
		if record:
			record_tests(program_name, tests_to_run, record_file_extension)
		else:
			test_results = run_tests(program_name, tests_to_run, record_file_extension)
			exit_code = display_results(test_results)
	else:
		print_error(f'directory \'{test_dir_name}\' does not exist or is not a directory')
		exit_code = 1

	return exit_code

if __name__ == '__main__':
	sys.exit(do_tests(sys.argv))
