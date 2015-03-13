#
#   Plotting needs
#   https://github.com/FVANCOP/ChartNew.js.git
#
#  In Morsel.js you need to make a change to the line
#      stack = middleware(DefaultHeaders, URLDecoder, CookieDecoder, BodyDecoder, MorselApp)
#  in the function start(app, port).
#   Becomes
#      stack = middleware(DefaultHeaders, URLDecoder, FileServer(pwd()), CookieDecoder, BodyDecoder, MorselApp, NotFound)
#
using Morsel
using DataFrames

include(string(ARGS[1], "/model.jl"))
using PartitionModel

cd(string(ARGS[1], "/html"))

app = Morsel.app()

function build_index()
  build_index("")
end

function build_index(tmp_fn::String)
  if isfile("css/site.min.css")
    index = replace(readall("index.html"), "/*css*/", readall("css/site.min.css"))
  else
    css_files = readdir("css")
    css = ""
    for f in css_files
      css = string(css, readall("css/" * f))
    end
    index = replace(readall("index.html"), "/*css*/", css)
  end

  if tmp_fn != ""
    index = replace(index, "{{output_class}}", "block")
    index = replace(index, "{{results_file}}", tmp_fn)
  else
    index = replace(index, "{{output_class}}", "none")
  end
  return index
end

get(app, "/") do req, res
  build_index()
end

get(app, "/solve") do req, res
  build_index()
end

post(app, "/solve") do req, res
  tl = parsefloat(req.state[:data]["timelimit"])
  fn = string(req.state[:data]["input_filename"])
  ng = parseint(req.state[:data]["ngroups"])
  println("Timelimit: " * string(tl) * " N: " * string(ng) * " Filename: " * fn)
  df = PartitionModel.Solve("uploads/" * fn, ng, tl)

  tmp_fn = "downloads/" * randstring(10) * ".csv"

  writetable(tmp_fn, df)
  rm("uploads/" * fn)

  return build_index(tmp_fn)
end

post(app, "/") do req, res
  fn = req.http_req.headers["X_FILENAME"]
  open(string("uploads/", fn), "w") do f
    write(f, req.http_req.data)
  end
  build_index()
end

start(app, 8080)
