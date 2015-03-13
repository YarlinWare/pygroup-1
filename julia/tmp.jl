cd("C:/Users/Oscar/Dropbox/Work/opti-group/julia")
include("model.jl")
using PartitionModel
s = "example_data.tsv"

df = readtable(s)

