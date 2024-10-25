# test.py
test.py is a basic test runner. It collects all test files in a given directory and evaluates them using the provided command, then displays this information to the user. It also provides the ability to evaluate the test cases and store their results for future testing.

## Usage
`./test.py <program command> <test case directory> [options]`

## Options
### Test Case Command
The command that will be run for each test case can either be simple or complex.
If the command can be written in the form `<command> <test case file>` then simply write `<command>`.
If the command requires more complexity, write out the command and replace all references to the test file with a `@`, which will be replaced at runtime with the name of the test case file. This symbol can be changed with the `-s <symbol>` and `--symbol <symbol>` options.

### Updating Test Cases
When run with the option `-u` or `--update`, all test cases will be evaluated and their results stored in record files for future test evaluations to check against.

### Test Case Customization
The file extension of test cases may be specified with `-e <extension>` and `--test-ext <extenision>`, or left empty, in which case all files except record files are tested.

The record file extension may be specified with `-r <extension>` and `--record-ext <extenision>`, or left empty, in which case it defaults to '.rec'.

These two may not be the same, and test.py will error if they are.
