import multiprocessing
import logging

import jimi

logging.basicConfig(level=logging.DEBUG)

def startWorker(systemId,systemIndex,manager):
    logging.info("Index %i booting on system %i",systemIndex,systemId)
    logging.info("Starting worker handler")
    workerHandler = jimi.workers.workerHandler()
    logging.info("Starting scheduler")
    scheduler = jimi.scheduler._scheduler(workerHandler,systemId,systemIndex)
    scheduler.handler()

if __name__ == "__main__":
    import os
    systemId = jimi.cluster.getSystemId()
    logging.info("System starting system_id is %i",systemId)

    # File system integrity
    logging.info("Checking cluster integrity")
    checksum = jimi.system.fileIntegrityRegister()
    logging.debug("System integrity hash generated. hash=%s",checksum)
    masterId = jimi.cluster.getMasterId()
    clusterMember = jimi.cluster.getClusterMemberById(systemId)
    masterMember = jimi.cluster.getMaster()
    logging.info("Current jimi master is on %i",masterId)
    if masterId != systemId and checksum != masterMember.checksum:
        logging.debug("Fixing file integrity mismatch using master")
        checksum = jimi.system.fixChecksum(masterId)
        if checksum != masterMember.checksum:
            logging.error("Checksum mismatch between system %i and master %i",systemId,masterId)
    clusterMember.checksum = checksum
    clusterMember.update(["checksum"])

    # Loading API
    apiSettings = jimi.settings.config["api"]["core"]
    jimi.api.createServer("jimi_core")
    logging.info("Starting API interface on %s:%i",apiSettings["bind"],apiSettings["port"])
    jimi.api.startServer(host=apiSettings["bind"], port=apiSettings["port"], threaded=True)

    # Starting workers
    manager = multiprocessing.Manager() # Need to replace this so that the cluster controls this without sharing a variable as this does not scale for containers
    cpuCount = os.cpu_count()
    systemIndexes = []
    logging.debug("Detected %i CPU",cpuCount)
    if cpuCount == 1:
        logging.info("Selected single cluster mode")
        systemIndexes.append({ "systemIndex" : 1, "manager" : manager.dict({ "lastHandle" : 0, "assigned" : 0 })})
    else:
        logging.info("Selected multi cluster mode")
        for index in range(1,len(cpuCount)):
            systemIndexes.append({ "systemIndex" : index, "manager" : manager.dict({ "lastHandle" : 0, "assigned" : 0 })})
    for systemIndex in systemIndexes:
        logging.debug("Starting index %i",systemIndex["systemIndex"])
        p = multiprocessing.Process(target=startWorker,args=(systemId,systemIndex["systemIndex"],systemIndex["manager"]))
        p.start()

    logging.info("Starting cluster processing")
    cluster = jimi.cluster._cluster()
    cluster.handler(systemIndexes)
