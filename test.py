
import sys
import os
import subprocess
from typing import *


def print_usage(this_name: str, error: str) -> None:
	print(f'error: {error}')
	print('Usage:')
	print(f'{this_name} <program name> <tests folder> [-ext <test file extension>] [-record]')


def is_valid_file(filename: str) -> bool:
	return os.path.exists(filename) and os.path.isfile(filename)


def is_valid_dir(dirname: str) -> bool:
	return os.path.exists(dirname) and os.path.isdir(dirname)


def get_tests(test_dir_name: str, test_ext: Optional[str]) -> Optional[list[str]]:
	if is_valid_dir(test_dir_name):
		all_items = [os.path.join(test_dir_name, fn) for fn in os.listdir(test_dir_name)]
		matches = [fp for fp in all_items if is_valid_file(fp)]
		if test_ext is not None:
			matches = [fp for fp in matches if fp.endswith(test_ext)]
		return matches
	else:
		return None


def record_path_of(path: str, record_ext: str) -> str:
	(base, ext) = os.path.splitext(path)
	return base + record_ext


def read_record_of(code_path: str, record_ext: str) -> Optional[bytes]:
	record_path = record_path_of(code_path, record_ext)
	if is_valid_file(record_path):
		with open(record_path, 'rb') as record:
			return record.read()
	else:
		print(f'record {record_path} does not exist, skipping...')
		return None


def write_record_of(code_path: str, record_ext: str, output: bytes) -> None:
	record_path = record_path_of(code_path, record_ext)
	with open(record_path, 'wb') as record:
		record.write(output)


# TODO: this assumes that `prog file` is enough to run a test.
# change program_name in args to program_run_format with some special
# character to indicate where the filepath goes
# so something like: `./main % -run` would execute with % replaced by the test case name
def run_and_capture(prog_name: str, code_path: str) -> bytes:
	print(f'TEST: {prog_name} {code_path}')
	process = subprocess.run([prog_name, code_path], capture_output=True)
	return process.stdout


def record_tests(prog_name: str, tests: list[str], record_ext: str) -> None:
	for test in tests:
		actual = run_and_capture(prog_name, test)
		write_record_of(test, record_ext, actual)


def run_tests(prog_name: str, tests: list[str], record_ext: str) -> list[tuple[str, bytes, bytes]]:
	results = []

	for test in tests:
		expected = read_record_of(test, record_ext)
		if expected is not None:
			actual = run_and_capture(prog_name, test)
			results.append((test, expected, actual))

	return results


def did_test_pass(expected: bytes, actual: bytes) -> bool:
	return expected == actual


def print_failure(test_name: str, expected: bytes, actual: bytes) -> None:
	print(f"   TEST FAILED")
	print(f"      EXPECTED: {expected!r}")
	print(f"      ACTUAL: {actual!r}")


def display_results(results: list[tuple[str, bytes, bytes]]) -> int:
	tests_passed = 0

	for (test_name, expected, actual) in results:
		passed = did_test_pass(expected, actual)

		if passed:
			tests_passed += 1
		else:
			print_failure(test_name, expected, actual)

	total_tests = len(results)
	print(f'{tests_passed}/{total_tests} tests passed')

	# return success if all tests passed, else failure
	return 0 if tests_passed == total_tests else 1

def do_tests() -> int:
	test_extension = None
	record_extension = ".rec"

	argv = sys.argv

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

	tests_to_run = get_tests(test_dir_name, test_extension)

	if tests_to_run is not None:
		if record:
			record_tests(program_name, tests_to_run, record_extension)
		else:
			test_results = run_tests(program_name, tests_to_run, record_extension)
			exit_code = display_results(test_results)
	else:
		print(f'error: directory \'{test_dir_name}\' does not exist or is not a directory')
		exit_code = 1

	return exit_code

if __name__ == '__main__':
	sys.exit(do_tests())
