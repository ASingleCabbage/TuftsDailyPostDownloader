import os, sys, json, math, csv
import urllib.request
from bs4 import BeautifulSoup
from furl import furl
from collections import namedtuple
from PyQt5 import QtNetwork, QtCore
from PyQt5.QtCore import QUrl, QObject, QThread, pyqtSignal
from functools import partial

class PostDownloader:
    def __init__(self, appWindow):
        self.saveLocation = None
        self.targetPostCount = None
        self.responses_raw = None
        self.appWindow = appWindow
        self.currentRequest = 0
        self.totalRequests = 0

        self.netManager = QtNetwork.QNetworkAccessManager()
        self.postProcessor = ResponsePostProcessor()
        self.additionalPostProcessor = AdditionalPostProcessor()
        self.thread = QThread()
        self.postProcessor.cleanProgressSignal.connect(self.cleanProgressCallback)
        self.postProcessor.cleanCompleteSignal.connect(self.cleanCompleteCallback)
        self.postProcessor.dumpCompleteSignal.connect(self.killThread)

        self.additionalPostProcessor.dumpCompleteSignal.connect(self.killThread)
        self.additionalPostProcessor.cleanCompleteSignal.connect(self.cleanCompleteCallback)

    def resetDownloader(self):
        self.currentRequest = 0
        self.totalRequests = 0
        self.responses_raw = list()

    def updateProgressBar(self):
        return

    def cleanProgressCallback(self, completeness):
        print('cleaning: ', completeness)
        return

    def cleanCompleteCallback(self):
        print('clean complete')
        return

    #kill thread not being called
    def killThread(self):
        print('killing thread')
        self.thread.quit()
        # self.thread.wait()

    def __startPP(self, processor, enablePP, connectFunc):
        print('starting post processor')
        #TODO: generate post processor on the fly?
        processor.saveLocation = self.saveLocation
        processor.jsonList = self.responses_raw
        processor.targetPostCount = self.targetPostCount
        processor.enablePP = enablePP
        self.thread.started.connect(connectFunc)
        self.postProcessor.moveToThread(self.thread)
        self.thread.start()

    def __probeRequest(self, url):
        RequestInfo = namedtuple('RequestInfo', 'code totalPosts')
        url.args['per_page'] = 1
        connection = urllib.request.urlopen(url.url)
        return RequestInfo(connection.getcode(), int(connection.getheader('x-wp-total')))

    #sets up relevant parameters for downloading and callback function, then starts first download
    #subsequent downloads are done by the callback function/handler
    def __downloadChunk(self, url, handler):
        self.appWindow.ui.statusBar.showMessage('Downloading, this may take a while... ')
        self.resetDownloader()
        assert(self.targetPostCount >= -1), 'Assertion failed: postCount invalid'
        if(self.targetPostCount == -1):
            self.targetPostCount = sys.maxsize        #this might be very bad practice D:

        info = self.__probeRequest(url)
        if(info.code != 200):
            print('Error: server responded with code {}'.format(info.code))
            raise ConnectionError('Server responded with code {}'.format(info.code))
        elif(info.totalPosts == 0):
            print('Error: no posts found with the given parameter')
            raise ValueError('No posts found with the given parameter')

        self.totalRequests = math.ceil(min(info.totalPosts, self.targetPostCount) / 100)
        self.netManager.finished.connect(handler)
        url.args['per_page'] = 100
        url.args['offset'] = 0
        print('Request: ', url.url)
        self.currentRequest += 1
        self.netManager.get(QtNetwork.QNetworkRequest(QUrl(url.url)))


    def getAdditional(self, url, outfile, convertCsv):
        self.saveLocation = outfile
        self.targetPostCount = -1
        def addRespHandler(reply):
            if(reply.error() == QtNetwork.QNetworkReply.NoError):
                response_string = str(reply.readAll(), 'utf-8').strip()
                if(not response_string):
                    raise ValueError('Response string is empty')    #this error happens when we call the function a second time D:

                response_array = json.loads(response_string) #not sure why we need strip() here but not in getJsonList
                self.responses_raw += response_array

                #TODO: might be better to send signal to AppWindow and let it handle this?
                self.appWindow.ui.progressBar.setValue(self.currentRequest / self.totalRequests * 80.0)

                if(len(response_array) == 100):
                    url.args['offset'] += 100
                    print('Request: ', url.url)
                    self.currentRequest += 1
                    self.netManager.get(QtNetwork.QNetworkRequest(QUrl(url.url)))
                else:
                    self.appWindow.ui.statusBar.showMessage('Cleaning up posts, this may take a while... ')
                    self.__startPP(self.additionalPostProcessor, convertCsv, self.additionalPostProcessor.cleanResponseList)
            else:
                print('Error occurred: ', reply.error())
                print(reply().errorString())
                #TODO: raise exception here and let AppWindow handle it
        self.__downloadChunk(url, addRespHandler)

    # url is a furl object
    # use -1 for no postCount limit
    def getJsonList(self, url, postCount, saveLocation, enablePP):
        self.saveLocation = saveLocation
        self.targetPostCount = postCount
        def respHandler(reply):
            if(reply.error() == QtNetwork.QNetworkReply.NoError):
                response_array = json.loads(str(reply.readAll(), 'utf-8'))
                self.responses_raw += response_array

                #TODO: might be better to send signal to AppWindow and let it handle this?
                self.appWindow.ui.progressBar.setValue(self.currentRequest / self.totalRequests * 80.0)

                if(len(self.responses_raw) < self.targetPostCount and len(response_array) == 100):
                    url.args['offset'] += 100
                    print('Request: ', url.url)
                    self.currentRequest += 1
                    self.netManager.get(QtNetwork.QNetworkRequest(QUrl(url.url)))
                else:
                    self.appWindow.ui.statusBar.showMessage('Cleaning up posts, this may take a while... ')
                    self.__startPP(self.postProcessor, enablePP, self.postProcessor.cleanResponseList)
            else:
                print('Error occurred: ', reply.error())
                print(reply().errorString())
                #TODO: raise exception here and let AppWindow handle it
        self.__downloadChunk(url, respHandler)


class ResponsePostProcessor(QObject):
    cleanProgressSignal = pyqtSignal(float)     #currently not used yet
    cleanCompleteSignal = pyqtSignal()
    dumpCompleteSignal = pyqtSignal()

    def __init__(self):
        super(ResponsePostProcessor, self).__init__()
        self.saveLocation = None
        self.jsonList = None
        self.targetPostCount = None
        self.enablePP = True

    def __processComplete(self):
        self.saveLocation = None
        self.jsonList = None
        self.targetPostCount = None
        self.dumpCompleteSignal.emit()

    def __htmlToPlainText(self, raw_html):
        soup = BeautifulSoup(raw_html, 'html5lib')
        return soup.get_text()

    def __dumpJsonList(self, jsons):
        print('dumping file to ', self.saveLocation)
        file = open(self.saveLocation, 'w', encoding='utf8')
        json.dump(jsons, file, indent=4, sort_keys=True, ensure_ascii=False)
        file.close()
        self.__processComplete()

    def __cleanResponse(self, json):
        del json['_links']
        del json['comment_status']
        json['content_text'] = self.__htmlToPlainText(json['content']['rendered'])
        json['excerpt_text'] = self.__htmlToPlainText(json['excerpt']['rendered'])
        del json['excerpt']
        del json['content']
        del json['meta']
        del json['status']
        del json['sticky']
        del json['template']
        del json['type']
        del json['ping_status']
        del json['format']
        json['guid'] = json['guid']['rendered']
        json['title_text'] = self.__htmlToPlainText(json['title']['rendered'])
        del json['title']
        return json

    def cleanResponseList(self):
        if(self.enablePP):
            print('cleaning up list')
            # listLength = len(jsonList)
            # iteration = 0
            responses_clean = []
            #weird bug here
            if(self.jsonList == None):
                print('Time travel bug workaround triggered')
                return
            for x in self.jsonList:
                x = self.__cleanResponse(x)
                #only include posts with text content
                if (x['content_text']):
                    responses_clean.append(x)
                # iteration += 1
                # self.cleanProgressSignal.emit(iteration / listLength) #possible bottleneck?
        else:
            responses_clean = self.jsonList
            print('Skipping post processing')

        self.cleanCompleteSignal.emit()
        if(len(responses_clean) > self.targetPostCount):
            self.__dumpJsonList(responses_clean[:self.targetPostCount])
        else:
            self.__dumpJsonList(responses_clean)

#TODO: some sort of inheritance maybe?
class AdditionalPostProcessor(QObject):
        cleanCompleteSignal = pyqtSignal()
        dumpCompleteSignal = pyqtSignal()

        def __init__(self):
            super(AdditionalPostProcessor, self).__init__()
            self.saveLocation = None
            self.jsonList = None
            self.targetPostCount = None     #added for compatibility reasons
            self.enablePP = True

        def __processComplete(self):
            self.saveLocation = None
            self.jsonList = None
            self.targetPostCount = None
            self.enablePP = None
            self.dumpCompleteSignal.emit()

        def __dumpJsonList(self, jsons):
            print('dumping file to ', self.saveLocation)
            file = open(self.saveLocation, 'w', encoding='utf8')
            json.dump(jsons, file, indent=4, sort_keys=True, ensure_ascii=False)
            file.close()

        def __dumpCsv(self, data):
            filename, _ = os.path.splitext(self.saveLocation)
            filename += '.csv'
            with open(filename, 'w', encoding='utf-8', newline='') as csvfile:
                fieldnames = ['id', 'name', 'slug', 'count', 'link']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                csvRow = {}
                for x in data:
                    csvRow['id'] = x['id']
                    csvRow['name'] = x['name']
                    csvRow['slug'] = x['slug']
                    csvRow['count'] = x['count']
                    csvRow['link'] = x['link']
                    writer.writerow(csvRow)
            print('Also created csv file {}'.format(filename))

        # TODO might want to catch KeyError
        def __cleanResponse(self, json):
            del json['_links']
            del json['meta']
            del json['taxonomy']
            del json['description']
            if 'parent' in json:
                del json['parent']
            return json

        def cleanResponseList(self):
            responses_clean = []
            #weird bug here
            if(self.jsonList == None):
                print('Time travel bug workaround triggered - additional PP')
                return
            for x in self.jsonList:
                x = self.__cleanResponse(x)
                responses_clean.append(x)
            self.cleanCompleteSignal.emit()
            self.__dumpJsonList(responses_clean)
            self.__dumpCsv(responses_clean)
            self.__processComplete()
