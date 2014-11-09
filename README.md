pygroup
===============

This software takes a set of entities and divides them into equal groups based on numeric and categorical variables.

+ For categorical variables, the model attempts to allocate entities so there are an equal number of entities who correspond to a particular category in each group.

+ For numerical variables, the model attempts to make the mean and variance of the variable the same for every group.

It is based on a similar, Excel based solution: group-allocator (https://github.com/odow/group-allocator). 

pygroup can read data either from a database or tab-delimited flat files.

Check the example.py file for usage and instructions.


## Requirements

+ Python 2.7
+ PuLP, an LP modeller for Python, which you can get here: https://projects.coin-or.org/PuLP
+ PYODBC which you can get here:
https://code.google.com/p/pyodbc/downloads/list

## Files
+ pygroup.py - python code
+ example.py - example usage
+ classification.txt - example file showing format. Used by example.py
+ entity_data.txt - example file showing format. Used by example.py

## Licensing
This software is distributed under the GNU GPLv2.0
