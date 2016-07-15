import time
import json
import uuid
import os
import re
import multiprocessing

import web
import numpy as np

from nupic.research.spatial_pooler import SpatialPooler as SP

from htmschoolviz import SpWrapper

global spWrappers
spWrappers = {}

urls = (
  "/", "Index",
  "/client/(.+)", "Client",
  "/_sp/", "SPInterface",
  "/_sp/(.+)/history/(.+)", "SPHistory",
)
app = web.application(urls, globals())
render = web.template.render("tmpl/")


def templateNameToTitle(name):
  if name == "index": return ""
  title = name
  if "-" in title:
    title = title.replace("-", " ")
  return title.title()



class Index:


  def GET(self):
    with open("html/index.html", "r") as indexFile:
      return render.layout(
        "index",
        "HTM School Visualizations",
        indexFile.read()
      )



class Client:


  def GET(self, file):
    name = file.split(".")[0]
    path = "html/{}".format(file)
    with open(path, "r") as htmlFile:
      return render.layout(
        name,
        templateNameToTitle(name),
        htmlFile.read()
      )



class SPInterface:


  def POST(self):
    global spWrappers

    params = json.loads(web.data())
    sp = SP(**params)
    spId = str(uuid.uuid4()).split('-')[0]
    wrapper = SpWrapper(spId, sp)
    spWrappers[spId] = wrapper
    web.header("Content-Type", "application/json")
    return json.dumps({"id": spId})


  def PUT(self):
    requestStart = time.time()
    requestInput = web.input()
    encoding = web.data()

    getSynapses = "getConnectedSynapses" in requestInput \
                  and requestInput["getConnectedSynapses"] == "true"
    getPools = "potentialPools" in requestInput \
               and requestInput["potentialPools"] == "true"

    if "id" not in requestInput:
      print "Request must include a spatial pooler id."
      return web.badrequest()

    spId = requestInput["id"]

    if spId not in spWrappers:
      print "Unknown SP id {}!".format(spId)
      return web.badrequest()


    sp = spWrappers[spId]

    learn = True
    if "learn" in requestInput:
      learn = requestInput["learn"] == "true"

    inputArray = np.array([int(bit) for bit in encoding.split(",")])

    print "Entering SP compute cycle...\n\tlearning on? {}".format(learn)

    response = sp.compute(inputArray, learn)

    web.header("Content-Type", "application/json")

    if getSynapses or getPools:
      response = sp.getCurrentState(
        getConnectedSynapses=getSynapses,
        getPotentialPools=getPools
      )

    self.saveSpStateInBackground(sp)

    jsonOut = json.dumps(response)
    requestEnd = time.time()
    print("\tSP compute cycle took %g seconds" % (requestEnd - requestStart))
    return jsonOut


  @staticmethod
  def saveSpStateInBackground(spWrapper):
    p = multiprocessing.Process(target=spWrapper.saveStateToRedis)
    p.start()



class SPHistory:

  def GET(self, spId, columnIndex):
    sp = spWrappers[spId]
    return sp.getConnectionHistoryForColumn(columnIndex)



if __name__ == "__main__":
  app.run()
