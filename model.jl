module PartitionModel

using DataFrames
using JuMP
using Cbc

export Solve

type PartitionData
  n::Int                                    # Number of entities
  df::DataFrame                             # Dataframe containing entity data
  Ids::DataArray                            # Array of entities
  vNum::Vector{Symbol}                      # Vector containing numeric variables
  vCat::Vector{Symbol}                      # Vector containing categoric variables
  nMet::Dict{Symbol, Dict{String, Float64}} # Numerical metrics
  cMet::Dict{Symbol, Dict{String, Float64}} # Categorical metrics
end

function Solve(fname::String, n_groups::Int, timelimit::Float64=999.9)
  Solve(CreateData(fname), n_groups, timelimit)
end

function GroupSize(m::Int, n::Int)
  k = floor(n / m)
  y = Array(Int, m)
  for g = 1:(n % m)
    y[g] = k + 1
  end
  for g = (n % m + 1) : m
    y[g] = k
  end
  return y
end

function Solve(data::PartitionData, n_groups::Int, timelimit::Float64=999.9)
  groups = GroupSize(n_groups, data.n)

  m = Model(solver=CbcSolver(seconds=timelimit))

  @defVar(m, x[1:length(data.Ids), 1:n_groups], Bin, string("x", i, j))
  @defVar(m, mmin[data.vNum])           # Minimum mean of group
  @defVar(m, mmax[data.vNum])           # Maximum mean of group
  @defVar(m, vmin[data.vNum])           # Minimum variance of group
  @defVar(m, vmax[data.vNum])           # Maximum variance of group
  @defVar(m, cvio[data.vCat] >= 0)           # Violation of categorical constraint


  k1 = 1.0
  k2 = 1.0
  k3 = 1000.0
  @setObjective(m, :Min,
                k1 * sum([(mmax[v] - mmin[v]) / data.nMet[v]["mean"] for v in data.vNum])
                + k2 * sum([(vmax[v] - vmin[v]) / data.nMet[v]["var"] for v in data.vNum])
                + k3 * sum(cvio)
                )

  # Each entity can only be allocated to single group
  @addConstraint(m, c1[i=1:data.n], sum([x[i,j] for j=1:n_groups]) == 1)

  # Set number of people per group
  @addConstraint(m, c2[j=1:n_groups], sum([x[i,j] for i=1:data.n]) == groups[j])

  # Bound numerical variables
  @addConstraint(m, cMeanMax[v=data.vNum, j=1:n_groups], sum([data.df[v][i] * x[i, j] for i=1:data.n]) >= groups[j] * mmin[v])
  @addConstraint(m, cMeanMin[v=data.vNum, j=1:n_groups], sum([data.df[v][i] * x[i, j] for i=1:data.n]) <= groups[j] * mmax[v])
  @addConstraint(m, cVarMax[v=data.vNum, j=1:n_groups], sum([(data.df[v][i] - data.nMet[v]["mean"])^2 * x[i, j] for i=1:data.n]) >= groups[j] * vmin[v])
  @addConstraint(m, cVarMax[v=data.vNum, j=1:n_groups], sum([(data.df[v][i] - data.nMet[v]["mean"])^2 * x[i, j] for i=1:data.n]) <= groups[j] * vmax[v])


  status = solve(m)

  if status == :Optimal || status == :UserLimit
    solution = get_solution(x, data)
    data.df[:Group] = solution
    return data.df
  elseif status == :Unbounded
    error("Unable to solve. Model is unbounded, which means something is wrong with your data")
  elseif status == :Error
    error("Cbc couldn't solve this model.")
  end
end

function get_solution(x, data::PartitionData)
  solution = Array(Int, data.n)
  for i = 1:data.n
    for j = 1:size(x, 2)
      if getValue(x[i, j]) > 0.5
        solution[i] = j
      end
    end
  end
  return solution
end

function CreateData(fname::String)
  df = readtable(fname)

  Ids = df[names(df)[1]]
  vNum = Array(Symbol, 0)
  vCat = Array(Symbol, 0)
  vMet = Dict{Symbol, Dict{String, Float64}} ()
  cMet = Dict{Symbol, Dict{String, Float64}} ()
  for v in names(df)[2:end]
    if typeof(df[v]) == DataArray{UTF8String, 1}
      push!(vCat, v)
      cMet[v] = categorical_metrics(df[v])
    else
      push!(vNum, v)
      vMet[v] = numerical_metrics(df[v])
    end
  end
  return PartitionData(length(Ids), df, Ids, vNum, vCat, vMet, cMet)
end

function numerical_metrics(c::DataArray{Float64, 1})
#   return Dict("mean" => mean(c), "var" => var(c))
  return {string("mean") => mean(c), string("var") => var(c)}

end

function categorical_metrics(c::DataArray{UTF8String, 1})
  metrics = Dict{String, Float64}()
  for i in c
    if haskey(metrics, string(i))
      metrics[string(i)] += 1.0
    else
      metrics[string(i)] = 1.0
    end
  end

  for (k, v) in metrics
    metrics[k] /= length(c)
  end
  return metrics
end


end

# s = "big_example.csv"
# df = PartitionModel.Solve(s, 20, 10.0)
