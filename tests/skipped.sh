# runs test cases that should be skipped
python3 ./test.py cat example-tests/invalid-json.txt
python3 ./test.py cat example-tests/missing-record.txt
python3 ./test.py cat example-tests/missing-stderr.txt
