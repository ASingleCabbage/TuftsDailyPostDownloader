import sys, os, webbrowser
import PyQt5
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog
from postDownloaderUI import Ui_PostDownloader
from queryBuilder import queryBuilder

class AppWindow(Ui_PostDownloader, QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_PostDownloader()
        self.ui.setupUi(self)

        defOutName = 'output.json'
        defOutFullPath = os.path.join(os.getcwd(), defOutName)
        self.ui.pathTextEdit.setPlainText(defOutFullPath)

        self.__query = queryBuilder(self)
        #might want to get all starting states by code (single point of truth?)
        self.__query.postLimitCount = self.ui.postCount.value()
        self.__query.catFilterRaw = self.ui.catTextEdit.toPlainText()
        self.__query.tagFilterRaw = self.ui.tagTextEdit.toPlainText()
        self.__query.startDate = self.ui.afterDateEdit.date().toPyDate().isoformat()
        self.__query.endDate = self.ui.beforeDateEdit.date().toPyDate().isoformat()
        self.__query.outputFullPath = defOutFullPath

        #TODO: should move everything UI based here
        self.__query.downloader.postProcessor.dumpCompleteSignal.connect(self.dumpCompleteCallback)

        #translating button names to valid endpoint parameters
        self.outputOptionDict = {'orderAuthorRB' : 'author',
                                 'orderDateRB' : 'date',
                                 'orderRelRB' : 'relevance',
                                 'orderTitleRB' : 'title',
                                 'orderIdRB' : 'id',
                                 'orderSlugRB' : 'slug'}

        self.outputOrderDict = {'ascendingRB' : 'asc', 'descendingRB' : 'desc'}

        self.show()

    def setCatFilter(self, isEnabled):
        assert(self.sender().objectName() == 'catFilterGroup')
        self.__query.catFilterEnabled = isEnabled

    def setTagFilter(self, isEnabled):
        assert(self.sender().objectName() == 'tagFilterGroup')
        self.__query.tagFilterEnabled = isEnabled

    def setOutputOrder(self):
        objName = self.sender().objectName()
        if(objName in self.outputOrderDict):
            self.__query.outputOrder = self.outputOrderDict[objName]
        elif(objName in self.outputOptionDict):
            self.__query.outputOption = self.outputOptionDict[objName]
        else:
            self.printStatus('Unknown object {} invoked setOutputOrder'.format(objName), 2000)

    def setPostLimit(self, hasLimit):
        assert(self.sender().objectName() == 'onlyRB')
        self.__query.postLimitEnabled = hasLimit

    def setDateFilter(self, isEnabled):
        objName = self.sender().objectName()
        if(objName == 'postsAfterCheckBox'):
            self.__query.startDateEnabled = isEnabled
        elif(objName == 'postsBeforeCheckBox'):
            self.__query.endDateEnabled = isEnabled
        else:
            self.printStatus('Unknown object {} invoked setDateFilter'.format(objName), 2000)

    def updateDateFilter(self):
        objName = self.sender().objectName()
        if(objName == 'afterDateEdit'):
            self.__query.startDate = self.sender().date().toPyDate().isoformat()
        elif(objName == 'beforeDateEdit'):
            self.__query.endDate = self.sender().date().toPyDate().isoformat()
        else:
            self.printStatus('Unknown object {} invoked updateDateFilter'.format(objName), 2000)

    def updatePostCount(self):
        assert(self.sender().objectName() == 'postCount')
        self.__query.postLimitCount = self.sender().value()
        return

    def updateCatFilter(self):
        assert(self.sender().objectName() == 'catTextEdit')
        self.__query.catFilterRaw = self.sender().toPlainText()

    def updateTagFilter(self):
        assert(self.sender().objectName() == 'tagTextEdit')
        self.__query.tagFilterRaw = self.sender().toPlainText()

    #TODO: add file extension to save file dialog
    def setOutputPath(self):
        #welp I just copied and pasted this code ¯\_(ツ)_/¯
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(self,'Create save file',os.getcwd(),'All Files (*)', options=options)
        if fileName:
            self.ui.pathTextEdit.setPlainText(fileName)
            self.__query.outputFullPath = fileName
        else:
            self.printStatus('Save file dialog canceled', 2000)

    def executeDownload(self):
        self.ui.progressBar.setValue(0)
        self.ui.execButton.setEnabled(False)
        try:
            self.__query.startDownload()
        except (ConnectionError, ValueError) as error:
            self.printStatus('Error: {}'.format(error), 4000)
        finally:
            self.ui.execButton.setEnabled(True)

    def launchGithubPage(self):
        #github repo
        webbrowser.open_new_tab('https://github.com/ASingleCabbage/TuftsDailyPostDownloader')
        return

    def launchHelpPage(self):
        #github wiki
        webbrowser.open_new_tab('https://github.com/ASingleCabbage/TuftsDailyPostDownloader/wiki')
        return

    def printStatus(self, message, duration=None):
        if(duration == None):
            self.ui.statusBar.showMessage(message)
        else:
            self.ui.statusBar.showMessage(message, duration)

    def dumpCompleteCallback(self):
        self.ui.progressBar.setValue(100)
        self.ui.execButton.setEnabled(True)
        self.printStatus('Download complete')

app = QApplication(sys.argv)
w = AppWindow()
w.show()
sys.exit(app.exec_())
