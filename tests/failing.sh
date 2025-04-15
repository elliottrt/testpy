# runs the example-tests that are expected to fail
python3 test.py cat example-tests/failing.txt

# example tests that should timeout
python3 test.py yes example-tests/failing.txt -T 10