Opti-Group
===============

This software takes a set of entities and divides them into equal groups based on numeric and categorical variables.

It is based on a similar, Excel based solution group-allocator (https://github.com/odow/group-allocator). 


## Requirements

+ Python 2.7
+ PuLP, an LP modeller for Python, which you can get here: https://projects.coin-or.org/PuLP
+ PYODBC which you can get here:
https://code.google.com/p/pyodbc/downloads/list

## Files
+ dataio.py - python code for getting data in appropriate format
+ model.py - python code that creates and solves optimisation model given an appropriate dataset.
+ example.py - example usage

## Licensing
This software is distributed under the GNU GPLv2.0
