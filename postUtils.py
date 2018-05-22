import os, sys, json, math
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

        self.postProcessor = ResponsePostProcessor()
        self.thread = QThread()
        self.postProcessor.cleanProgressSignal.connect(self.cleanProgressCallback)
        self.postProcessor.cleanCompleteSignal.connect(self.cleanCompleteCallback)
        self.postProcessor.dumpCompleteSignal.connect(self.killThread)

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

    def __startPostProcessor(self):
        print('starting post processor')
        self.postProcessor.saveLocation = self.saveLocation
        self.postProcessor.jsonList = self.responses_raw
        self.postProcessor.targetPostCount = self.targetPostCount
        self.postProcessor.moveToThread(self.thread)
        self.thread.started.connect(self.postProcessor.cleanResponseList)
        self.thread.start()

    def __probeRequest(self, url):
        RequestInfo = namedtuple('RequestInfo', 'code totalPosts')
        url.args['per_page'] = 1
        connection = urllib.request.urlopen(url.url)
        return RequestInfo(connection.getcode(), int(connection.getheader('x-wp-total')))
    # url is a furl object
    # use -1 for no postCount limit
    def getJsonList(self, url, postCount, saveLocation):
        self.appWindow.ui.statusBar.showMessage('Downloading, this may take a while... ')
        self.resetDownloader()
        def makeRequest(urlString):
            self.currentRequest += 1
            netManager.get(QtNetwork.QNetworkRequest(QUrl(urlString)))
        def respHandler(reply):
            if(reply.error() == QtNetwork.QNetworkReply.NoError):
                response_array = json.loads(str(reply.readAll(), 'utf-8'))
                self.responses_raw += response_array

                print('Response length: ', len(self.responses_raw))
                #might be better to send signal to AppWindow and let it handle this?
                self.appWindow.ui.progressBar.setValue(self.currentRequest / self.totalRequests * 80.0)

                if(len(self.responses_raw) < self.targetPostCount and len(response_array) == 100):
                    url.args['offset'] += 100
                    print('Request: ', url.url)
                    makeRequest(url.url)
                else:
                    self.appWindow.ui.statusBar.showMessage('Cleaning up posts, this may take a while... ')
                    self.__startPostProcessor()
            else:
                print('Error occurred: ', reply.error())
                print(reply().errorString())
                #TODO: raise exception here and let AppWindow handle it

        assert(postCount >= -1), 'Assertion failed: postCount invalid'
        if(postCount == -1):
            postCount = sys.maxsize        #this might be very bad practice D:

        self.saveLocation = saveLocation
        self.targetPostCount = postCount

        info = self.__probeRequest(url)
        if(info.code != 200):
            print('Error: server responded with code {}'.format(info.code))
            raise ConnectionError('Server responded with code {}'.format(info.code))
        elif(info.totalPosts == 0):
            print('Error: no posts found with the given parameter')
            raise ValueError('No posts found with the given parameter')

        print('total requests', math.ceil(min(info.totalPosts, postCount) / 100))
        self.totalRequests = math.ceil(min(info.totalPosts, postCount) / 100)

        netManager = QtNetwork.QNetworkAccessManager()
        netManager.finished.connect(respHandler)
        #iteration = 0
        url.args['per_page'] = 100
        url.args['offset'] = 0
        print('Request: ', url.url)
        makeRequest(url.url)

class ResponsePostProcessor(QObject):
    cleanProgressSignal = pyqtSignal(float)
    cleanCompleteSignal = pyqtSignal()
    dumpCompleteSignal = pyqtSignal()

    def __init__(self):
        super(ResponsePostProcessor, self).__init__()
        self.saveLocation = None
        self.jsonList = None
        self.targetPostCount = None

    def __processComplete(self):
        self.saveLocation = None
        self.jsonList = None
        self.targetPostCount = None
        self.dumpCompleteSignal.emit()

    def __htmlToPlainText(self, raw_html):
        soup = BeautifulSoup(raw_html, 'html5lib')
        return soup.get_text()

    def __dumpJsonAry(self, jsons):
        print('dumping file to ', self.saveLocation)
        file = open(self.saveLocation, 'w', encoding='utf8')
        file.write('[')
        for x in jsons:
            # ensure ascii false so json.dump won't print out escaped unicode
            json.dump(x, file, indent=4, sort_keys=True, ensure_ascii=False)
            file.write(',\n')
        file.seek(0, os.SEEK_END)
        pos = file.tell() - 3
        file.seek(pos, os.SEEK_SET)
        file.truncate()
        file.write(']')
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
        print('cleaning up list')
        # listLength = len(jsonList)
        # iteration = 0
        responses_clean = []
        #weird bug here
        if(self.jsonList == None):
            print('Time travel bug workaround triggered')
            return
        for x in self.jsonList:
            try:
                x = self.__cleanResponse(x)
            except KeyError:
                print('Key Error: ', x)
            #only include posts with text content
            if (x['content_text']):
                responses_clean.append(x)
            # iteration += 1
            # self.cleanProgressSignal.emit(iteration / listLength) #possible bottleneck?

        self.cleanCompleteSignal.emit()
        if(len(responses_clean) > self.targetPostCount):
            self.__dumpJsonAry(responses_clean[:self.targetPostCount])
        else:
            self.__dumpJsonAry(responses_clean)
