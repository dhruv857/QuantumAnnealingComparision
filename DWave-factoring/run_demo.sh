#!/bin/bash -i

module load factoring
for i in {1..61}
do
   python demo.py $i > results/$i.txt
done