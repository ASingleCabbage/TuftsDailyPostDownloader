from furl import furl
from collections import namedtuple
from postUtils import PostDownloader

#rename to query builder?
class queryBuilder():
    def __init__(self, appWindow):
        self.postLimitEnabled = False
        self.postLimitCount = 0
        self.outputOption = 'date'
        self.outputOrder = 'desc'

        self.startDateEnabled = False
        self.endDateEnabled = False
        self.startDate = None
        self.endDate = None

        self.catFilterEnabled = False
        self.tagFilterEnabled = False
        self.catFilterRaw = None
        self.tagFilterRaw = None

        self.searchTermEnabled = False
        self.searchTerm = ''

        self.postProcessEnabled = True
        self.convertCsvEnabled = True

        self.appWindow = appWindow
        self.downloader = PostDownloader(appWindow)
        #outputFullPath also contains the filename itself
        self.outputFullPath = None

    def startDownload(self):
        url = self.__buildURL()
        if(self.postLimitEnabled):
            self.downloader.getJsonList(url, self.postLimitCount, self.outputFullPath, self.postProcessEnabled)
        else:
            self.downloader.getJsonList(url, -1, self.outputFullPath, self.postProcessEnabled)

    def downloadAdditional(self, option, outfile):
        optionsDict = {'tags' : furl('https://tuftsdaily.com/wp-json/wp/v2/tags/'),
                       'categories' : furl('https://tuftsdaily.com/wp-json/wp/v2/categories/')}
        assert(option in optionsDict)
        self.downloader.getAdditional(optionsDict[option], outfile, self.convertCsvEnabled)

    def __buildURL(self):
        url = furl('https://tuftsdaily.com/wp-json/wp/v2/posts/')
        url.args['order'] = self.outputOrder
        url.args['orderby'] = self.outputOption
        # gotta add hh:mm:ss at the end as WP api takes in time too
        # WP filters with post local time instead of GMT time
        if(self.startDateEnabled):
            url.args['after'] = self.startDate + 'T00:00:00'
        if(self.endDateEnabled):
            url.args['before'] = self.endDate + 'T00:00:00'

        if(self.catFilterEnabled):
            catIds = self.__parseFilters(self.catFilterRaw)
            if(catIds.include):
                url.args['categories'] = catIds.include
            if(catIds.exclude):
                url.args['categories_exclude'] = catIds.exclude

        if(self.tagFilterEnabled):
            tagIds = self.__parseFilters(self.tagFilterRaw)
            if(tagIds.include):
                url.args['tags'] = tagIds.include
            if(tagIds.exclude):
                url.args['tags_exclude'] = tagIds.exclude
        return url

    #TODO: adapt filter parsing to work with real names
    # Currently parses ids only, returns named tuple of strings
    def __parseFilters(self, rawFilter):
        s = rawFilter.strip()
        includeList = list()
        excludeList = list()
        FilterIds = namedtuple('FilterIds', 'include exclude')
        #string evaluates to false if empty
        if(not s):
            return FilterIds('', '')

        rawList = s.split()
        for id in rawList:
            if(id[0] == '-'):
                excludeList.append(id[1:])
            else:
                includeList.append(id)
        return FilterIds(' '.join(includeList), ' '.join(excludeList))
