# @HEADER
# ************************************************************************
#
#            TriBITS: Tribal Build, Integrate, and Test System
#                    Copyright 2013 Sandia Corporation
#
# Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation,
# the U.S. Government retains certain rights in this software.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the Corporation nor the names of the
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY SANDIA CORPORATION "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL SANDIA CORPORATION OR THE
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# ************************************************************************
# @HEADER

try:
  # Python 2
  from urllib2 import urlopen
except ImportError:
  # Python 3
  from urllib.request import urlopen

import sys
import hashlib
import json
import datetime
import copy
import pprint

from FindGeneralScriptSupport import *
from GeneralScriptSupport import *


# Validate a date YYYY-MM-DD string and return a date object for the
# 'datetime' module.
# 
def validateAndConvertYYYYMMDD(dateText):
  try:
    return datetime.datetime.strptime(dateText, '%Y-%m-%d')
  except ValueError:
    raise ValueError("Incorrect data format for '"+dateText+"', should be YYYY-MM-DD")


# Get a file name string from a general text string.
#
# This replaces non-alphanumeric chars with '_'.
#
def getFileNameStrFromText(inputStr):
  fileNameStr = ""
  for char in inputStr:
    if char.isalnum():
      fileNameStr += char
    else:
       fileNameStr += "_"
  return fileNameStr


# Check if the key/value pairs for two dicts are the same and if return an
# error message explaining how they are different.
#
# Returns tuple (hasSameKeyValuePairs, errMsg).  If
# hasSameKeyValuePairs==True, then errMsg==None.  Otherwise, if
# hasSameKeyValuePairs==False, then errMsg gives a string that explains how
# they are different.
#
# This improves on a simple check dict_1 == dict_2 in that shows exactly why
# the dicts are different for a single key/value pair.
#
def checkDictsAreSame(dict_1, dict_1_name, dict_2, dict_2_name):
  # Assume all passing unless we find a difference
  hasSameKeyValuePairs = True
  errMsg = None
  # Check if they have the same number of keys
  if hasSameKeyValuePairs and (len(dict_1.keys()) != len(dict_2.keys())):
    hasSameKeyValuePairs = False
    errMsg = "len("+dict_1_name+".keys())="+str(len(dict_1.keys()))+\
      " != len("+dict_2_name+".keys())="+str(len(dict_2.keys()))
  # Check that they have the same key/value pairs
  if hasSameKeyValuePairs:
    for key_1 in dict_1.keys():
      if not key_1 in dict_2.keys():
        hasSameKeyValuePairs = False
        errMsg = dict_1_name+"['"+key_1+"'] does not exist in "+dict_2_name
        break
      keyVal_1 = dict_1[key_1]
      keyVal_2 = dict_2[key_1]
      if keyVal_1 != keyVal_2:
        hasSameKeyValuePairs = False
        errMsg = dict_1_name+"['"+key_1+"']="+str(keyVal_1)+" != "+\
          dict_2_name+"['"+key_1+"']="+str(keyVal_2)
        break
    #end for
  #end if
  # Return the final result
  return (hasSameKeyValuePairs, errMsg)


# Compress a long file name to avoid open() error
#
# If the full file name must be shorted and if prefix!="", then it is added to
# the beginning of the shortened filename.  Also, if ext!="", then "."+ext is
# added to the end of the shortened filename.  Otherwise, if inputFileName is
# not too long, then it is returned without modification (i.e. 'prefix' and
# 'ext' are ignored).  NOTE: If 'prefix' and 'ext' are too long, then the
# returned shortened filename may also be too long.
#
# This function should return a shorter unique file name that is platform
# independent.
#
def getCompressedFileNameIfTooLong(inputFileName, prefix="", ext=""):
  maxFileNameLength = 255 # ToDo: Figure out for this system?
  if len(inputFileName) > maxFileNameLength:
    hashObject = hashlib.sha1(inputFileName)
    hashStr = hashObject.hexdigest()
    newFileName = prefix+hashObject.hexdigest()
    if ext: newFileName += "." + ext
    return newFileName
  return inputFileName
    

# Filter and input list and return a list with elements where
# matchFunctor(inputList[i])==True.
#
def getFilteredList(inputList, matchFunctor):
  filteredList = []
  for ele in inputList:
    if matchFunctor(ele): filteredList.append(ele)
  return filteredList


# Filter an input list return a two lists (matchList, nomatchList) where the
# first list has elements where matchFunctor(inputList[i])==True and the
# second list has elements where matchFunctor(inputList[i])==False.
#
def splitListOnMatch(inputList, matchFunctor):
  #print("\nsplitListOnMatch(): matchFunctor = "+str(matchFunctor))
  matchList = []
  nomatchList = []
  for ele in inputList:
    if matchFunctor(ele): matchList.append(ele)
    else: nomatchList.append(ele)
  return (matchList, nomatchList)


# DECORATOR match functor class that negates the match of a stored functor.
#
class NotMatchFunctor(object):

  # Construct with another functor to negate
  def __init__(self, matchFunctor):
    self.__matchFunctor = matchFunctor

  # Convert to string rep for debugging/etc.
  def __str__(self):
    myStr = "NotMatchFunctor{"+str(self.__matchFunctor)+"}"
    return myStr

  # Negate the matchFunctor
  def __call__(self, item):
    return (self.__matchFunctor(item) == False)


# Apply a functor to transform every element in a list
#
# The object transformFunctor is applied as:
#
#   list_inout[i] = transformFunctor(list_inout[i])
#
# If the elements are small value-type objects, then the assignment is needed.
# However, if the list elements are handled with reference semantics like a
# list [] or a dict {} then really the object is being modified in place and
# the assignment is not needed but it cheap and harmess in that case.
#
# This returns the input list transformed but the return object can be ignored
# because it modifies the input list object's elements in place.
#
def foreachTransform(list_inout, transformFunctor):
  for i in xrange(len(list_inout)):
    list_inout[i] = transformFunctor(list_inout[i])
  return list_inout


# Remove elements from a list given a list of indexes
#
# This modifies the orginal list inplace but also returns it.  Therefore, if
# you want to keep the original list, you better create a copy of the base
# list object before passing it in.
#
def removeElementsFromListGivenIndexes(list_inout, indexesToRemoveList_in):
  indexesToRemoveList = copy.copy(indexesToRemoveList_in)
  indexesToRemoveList.sort()
  numRemoved = 0
  for index in indexesToRemoveList:
    del list_inout[index-numRemoved]
    numRemoved += 1
  return list_inout

# Given a CDash query URL PHP page that returns JSON data, return the JSON
# data converged to a Python data-structure.
#
# The returned Python object will be a simple nested set of Python dicts and
# lists.
#
# NOTE: This function can't really be unit tested becuase it actually gets
# data from CDash.  Therefore, the code below will be structured such that it
# we can avoid getting call it in any automated tests.
#
def extractCDashApiQueryData(cdashApiQueryUrl):
  #print sys.version_info
  if sys.version_info < (2,7,9):
    raise Exception("Error: Must be using Python 2.7.9 or newer")
  # NOTE: If we use Python 2.6.6. then the urllib2 function crashes!
  response = urlopen(cdashApiQueryUrl)
  return json.load(response)


# Color HTML text in red
def makeHtmlTextRed(htmlText):
  return("<font color=\"red\">"+htmlText+"</font>")


# Color HTML text in grean
def makeHtmlTextGreen(htmlText):
  return("<font color=\"green\">"+htmlText+"</font>")


# Read a CSV file into a list of dictionaries for each row where the rows of
# the output list are dicts with the column names as keys.
#
# For example, for the CSV file:
#
#   col_0, col_1, col_2
#   val_00, val_01, val_02
#   val_10, val_11, val_12
#
# the returned list of dicts will be:
#
#  [
#    { 'col_0':'val_00', 'col_1':'val_01', 'col_2':'val_02' }, 
#    { 'col_0':'val_10', 'col_1':'val_11', 'col_2':'val_12' }, 
#    ]
#
# and the expected list of column headers would be:
#
#   expectedColumnHeadersList = [ 'col_0', 'col_1', 'col_2' ]
#
# But the expectedColumnHeadersList argument is optional.
#
def readCsvFileIntoListOfDicts(csvFileName, expectedColumnHeadersList=None):
  listOfDicts = []
  with open(csvFileName, 'r') as csvFile:
    # Get the list of column headers
    columnHeadersLineStr = csvFile.readline().strip()
    columnHeadersRawStrList = columnHeadersLineStr.split(',')
    columnHeadersList = []
    for headerRawStr in columnHeadersRawStrList:
      columnHeadersList.append(headerRawStr.strip())
    if expectedColumnHeadersList:
      if len(columnHeadersList) != len(expectedColumnHeadersList):
        raise Exception(
          "Error, for CSV file '"+csvFileName+"' the"+\
          " column headers '"+str(columnHeadersList)+"' has"+\
          " "+str(len(columnHeadersList))+" items but the expected"+\
          " set of column headers '"+str(expectedColumnHeadersList)+"'"+\
          " has "+str(len(expectedColumnHeadersList))+" items!")
      for i in range(len(columnHeadersList)):
        if columnHeadersList[i] != expectedColumnHeadersList[i]:
          raise Exception(
            "Error, column header "+str(i)+" '"+columnHeadersList[i]+"' does"+\
            " not match expected column header '"+expectedColumnHeadersList[i]+"'!")
    # Read the rows of the CSV file into dicts
    dataRow = 0
    line = csvFile.readline().strip()
    while line:
      #print("\ndataRow = "+str(dataRow))
      lineList = line.split(',')
      #print(lineList)
      # Assert that the row has the right number of entries
      if len(lineList) != len(columnHeadersList):
        raise Exception(
          "Error, data row "+str(dataRow)+" '"+line+"' has"+\
          " "+str(len(lineList))+" entries which does not macth"+\
          " the number of column headers "+str(len(columnHeadersList))+"!")
      # Read the row entries into a new dict
      rowDict = {}
      for j in range(len(columnHeadersList)):
        rowDict.update( { columnHeadersList[j] : lineList[j].strip() } )
      #print(rowDict)
      listOfDicts.append(rowDict)
      # Update for next row
      line = csvFile.readline().strip()
      dataRow += 1
  # Return the constructed object
  return listOfDicts


# Get list of expected builds from CSV file
def getExpectedBuildsListfromCsvFile(expectedBuildsFileName):
  return readCsvFileIntoListOfDicts(expectedBuildsFileName,
    ['group', 'site', 'buildname'])


# Get list of tests from CSV file
def getTestsWtihIssueTrackersListFromCsvFile(testsWithIssueTrackersFile):
  return readCsvFileIntoListOfDicts(testsWithIssueTrackersFile,
      ['site', 'buildName', 'testname', 'issue_tracker_url', 'issue_tracker'])


# Print print a nested Python data-structure to a file
#
# ToDo: Reimplement this to create a better looking set of indented that that
# involves less right-drift and the expense of more vertical space.
#
def pprintPythonDataToFile(pythonData, filePath):
  pp = pprint.PrettyPrinter(stream=open(filePath,'w'), indent=2)
  pp.pprint(pythonData)


# Get data off CDash and cache it or read from previously cached data.
#
# If useCachedCDashData == True, then the file cdashQueryDataCacheFile must
# exist and will be used to get the data instead of calling CDash
#
# If alwaysUseCacheFileIfExists==True and the file cdashQueryDataCacheFile
# already exists, then the file cdashQueryDataCacheFile will be used to get
# the dta instead of callig CDash.
#
# Otherwise, CDash will be called at cdashQueryUrl to get the data and then
# the data will be written to the the file cdashQueryDataCacheFile if
# cdashQueryDataCacheFile != None.
#
# This function can be used to get data off of CDash using any page on CDash
# including cdash/api/v1/index.php, cdash/api/v1/queryTests.php and anything
# other PHP page that returns a JSON data structure (which is all of the
# cdash/api/v1/XXX.php pages).
#
def getAndCacheCDashQueryDataOrReadFromCache(
  cdashQueryUrl,
  cdashQueryDataCacheFile,  # File name
  useCachedCDashData,  # If 'True', then cdasyQueryDataCacheFile must be non-null
  alwaysUseCacheFileIfExists = False,
  verbose = False,
  extractCDashApiQueryData_in=extractCDashApiQueryData,
  ):
  if (
      alwaysUseCacheFileIfExists \
      and cdashQueryDataCacheFile \
      and os.path.exists(cdashQueryDataCacheFile) \
    ):
    if verbose:
      print("  Since the file exists, using cached data from file:\n"+\
        "    "+cdashQueryDataCacheFile )
    cdashQueryData=eval(open(cdashQueryDataCacheFile, 'r').read())
  elif useCachedCDashData:
    if verbose:
      print("  Using cached data from file:\n    "+cdashQueryUrl )
    cdashQueryData=eval(open(cdashQueryDataCacheFile, 'r').read())
  else:
    if verbose:
      print("  Downloading CDash data from:\n    "+cdashQueryUrl )
    cdashQueryData = extractCDashApiQueryData_in(cdashQueryUrl)
    if cdashQueryDataCacheFile:
      if verbose:
        print("  Caching data downloaded from CDash to file:\n    "+\
          cdashQueryDataCacheFile)
      pprintPythonDataToFile(cdashQueryData, cdashQueryDataCacheFile) 
  return cdashQueryData


# Construct full cdash/api/v1/index.php query URL to pull data down given the
# pieces
def getCDashIndexQueryUrl(cdashUrl, projectName, date, filterFields):
  if date: dateArg = "&date="+date
  else: dateArg = "" 
  return cdashUrl+"/api/v1/index.php?project="+projectName+dateArg \
    + "&"+filterFields


# Construct full cdash/index.php browser URL given the pieces
def getCDashIndexBrowserUrl(cdashUrl, projectName, date, filterFields):
  if date: dateArg = "&date="+date
  else: dateArg = "" 
  return cdashUrl+"/index.php?project="+projectName+dateArg \
    + "&"+filterFields


# Construct full cdash/api/v1/queryTests.php query URL given the pieces
def getCDashQueryTestsQueryUrl(cdashUrl, projectName, date, filterFields):
  if date: dateArg = "&date="+date
  else: dateArg = "" 
  return cdashUrl+"/api/v1/queryTests.php?project="+projectName+dateArg+"&"+filterFields


# Construct full cdash/queryTests.php browser URL given the pieces
def getCDashQueryTestsBrowserUrl(cdashUrl, projectName, date, filterFields):
  if date: dateArg = "&date="+date
  else: dateArg = "" 
  return cdashUrl+"/queryTests.php?project="+projectName+dateArg+"&"+filterFields


# Copy a key/value pair from one dict to another if it eixsts
def copyKeyDictIfExists(sourceDict_in, keyName_in, dict_inout):
  value = sourceDict_in.get(keyName_in, None)
  if value:
    dict_inout.update( { keyName_in : value } )


# Collect CDash index.php build summary fields
#
# Change this to get all of the fields and add the 'group' field as well.
#
def collectCDashIndexBuildSummaryFields(fullCDashIndexBuild, groupName):
  summaryBuild = { u'group' : groupName }
  copyKeyDictIfExists(fullCDashIndexBuild, u'site', summaryBuild)
  copyKeyDictIfExists(fullCDashIndexBuild, u'buildname', summaryBuild)
  copyKeyDictIfExists(fullCDashIndexBuild, u'update', summaryBuild)
  copyKeyDictIfExists(fullCDashIndexBuild, u'configure', summaryBuild)
  copyKeyDictIfExists(fullCDashIndexBuild, u'compilation', summaryBuild)
  copyKeyDictIfExists(fullCDashIndexBuild, u'test', summaryBuild)
  return summaryBuild


# Given the full Python JSON data-structure returned from the page
# cdash/api/v1/index.php query from extractCDashApiQueryData(), return a
# flattened-out data-structure that is easier to manipulate.
#
# This function takes in the JSON data-structure (as a nested set of Python
# dicts and listed) directly returned from a query gotten from the page
# cdash/api/v1/index.php with some filters.
#
# The input full CDash index.php JSON data-structure has the following
# structure and fields of interest:
#
#  fullCDashIndexBuildsJson =
#  {
#    'all_buildgroups': [ {'id':1,'name:"Nightly"}, ...],
#    'buildgroups': [
#      {
#        'name':"???",   # group name, e.g. Nightly
#        'builds":[
#          {
#            'site':"???"
#            'buildname':"???",
#            'update': {'errors':???, ...},
#            'configure':{'error': ???, ...},
#            'compilation':{'error': ???, ...},
#            'test': {'fail':???, 'notrun':???, 'pass':???, ...},
#            ...
#            },
#            ...
#          ]
#        },
#        ...
#      ...
#      ]
#      },
#      ...
#    }
#
# This function gets the data from *all* of the collapsed builds and returns
# the flatten-out list of dicts for each build with the 'group' field added in
# as:
#
#   [
#     {
#       'group':"???",
#       'site':"???",
#       'buildname':"???",
#       'update': {'errors':???, ...},
#       'configure':{'error': ???, ...},
#       'compilation':{'error': ???, ...},
#       'test': {'fail':???, 'notrun':???, 'pass':???, ...},
#       ...
#       },
#     ...
#     ]
#
# This collects *all* of the builds from all of the build groups provided by
# that data-structure, not just the 'Nighlty' build group.  Therefore, if you
# want to only consider one set of build groups, you need to add that to the
# CDash query URL (e.g. group='Nighlty').
#
def flattenCDashIndexBuildsToListOfDicts(fullCDashIndexBuildsJson):
  summaryCDashIndexBuilds = []
  for buildgroup in fullCDashIndexBuildsJson["buildgroups"]:
    groupName = buildgroup["name"]
    for build in buildgroup["builds"]:
      summaryBuild = collectCDashIndexBuildSummaryFields(build, groupName)
      summaryCDashIndexBuilds.append(summaryBuild)
  return summaryCDashIndexBuilds


# Given the full JSON data-structure returned from the page
# cdash/api/v1/queryTests.php query from extractCDashApiQueryData(), return a
# flattened-out data-structure that is easier to manipulate.
#
# This function takes in the JSON data-structure (as a nested set of Python
# dicts and listed) directly returned from a query gotten from the page
# cdash/api/v1/queryTests.php with some filters.
#
# The input full CDash queryTests.php JSON data-structure has the following
# structure and fields of interest:
#
#  fullCDashQueryTestsJson =
#  {
#    'version':???,
#    'feed_enabled':???,
#    ...
#    'builds': [
#      {
#        'buildName': 'Trilinos-atdm-mutrino-intel-opt-openmp-HSW',
#        'buildSummaryLink': 'buildSummary.php?buildid=4109735',
#        'buildstarttime': '2018-10-29T05:54:03 UTC',
#        'details': 'Completed (Failed)\n',
#        'nprocs': 4,
#        'prettyProcTime': '40s 400ms',
#        'prettyTime': '10s 100ms',
#        'procTime': 40.4,
#        'site': 'mutrino',
#        'siteLink': 'viewSite.php?siteid=223',
#        'status': 'Failed',
#        'statusclass': 'error',
#        'testDetailsLink': 'testDetails.php?test=57925465&build=4109735',
#        'testname': 'Anasazi_Epetra_BKS_norestart_test_MPI_4',
#        'time': 10.1
#        },
#      ...
#      ],
#    ...
#    }
#
# This function gets the data from *all* of the tests and returns the
# flatten-out list of dicts with some additional fields for each test of the
# form:
#
#   [
#     {
#       'buildName': 'Trilinos-atdm-mutrino-intel-opt-openmp-HSW',
#       'buildSummaryLink': 'buildSummary.php?buildid=4109735',
#       'buildstarttime': '2018-10-29T05:54:03 UTC',
#       'details': 'Completed (Failed)\n',
#       'nprocs': 4,
#       'prettyProcTime': '40s 400ms',
#       'prettyTime': '10s 100ms',
#       'procTime': 40.4,
#       'site': 'mutrino',
#       'siteLink': 'viewSite.php?siteid=223',
#       'status': 'Failed',
#       'statusclass': 'error',
#       'testDetailsLink': 'testDetails.php?test=57925465&build=4109735',
#       'testname': 'Anasazi_Epetra_BKS_norestart_test_MPI_4',
#       'time': 10.1,
#       },
#     ...
#     ]
#
# NOTE: This does a shallow copy so any modifications to the returned list and
# dicts will modify the original data-structure fullCDashQueryTestsJson.  If
# that is a problem, then make sure and do a deep copy before passing in
# fullCDashQueryTestsJson.
#
# This collects *all* of the tests from all of the "build" list provided by
# the CDash JSON data-structure.  Therefore, if you want to only consider one
# set of build groups, you need to add that to the CDash query URL
# (e.g. buildName='<build-name>').
#
def flattenCDashQueryTestsToListOfDicts(fullCDashQueryTestsJson):
  testsListOfDicts = []
  for testDict in fullCDashQueryTestsJson['builds']:
    testsListOfDicts.append(testDict)
  return testsListOfDicts


# Create a lookup dict for a list of dicts
#
# listOfDicts [in/out]: List of dict objects that have keys that one will want
# to lookup the dict based on their values.  May have 100% duplicate elements
# removed from the list.
#
# listOfKeys [in]: List of the names of keys in these dicts that are used to
# build a search dict data-structure which is returned from this function.
#
# removeExactDuplicateElements [in]: If True, then dict elements that are 100%
# duplicates and have the exact same key/value pairs will be removed from
# listOfDicts. (default False)
#
# If listOfDicts has any elements that are 100% complete duplicates with the
# same exact key/value pairs, then the later elements will be removed from the
# list.  But if just the key/value pairs listed in listOfKeys are duplicated
# but one or more of the other key/value pairs is different, then then an
# excpetion is thrown.
#
# NOTE: This is an implementation function that is used in the class
# SearchableListOfDicts.  Please use that class instead of this raw function.
#
def createLookupDictForListOfDicts(listOfDicts, listOfKeys,
  removeExactDuplicateElements=False,
  ):
  # Build the lookup dict data-structure. Also, optionally mark any 100%
  # duplicate elements if asked to remove 100% duplicate elements.
  lookupDict = {} ; idx = 0 ; numRemoved = 0 ; duplicateIndexesToRemoveList = []
  for dictEle in listOfDicts:
    # Create the structure of recursive dicts for the keys in order
    currentLookupDictRef = lookupDict
    lastLookupDictRef = None
    lastKeyValue = None
    for key in listOfKeys:
      keyValue = dictEle[key]
      lastLookupDictRef = currentLookupDictRef
      lastKeyValue = keyValue
      nextLookupDictRef = currentLookupDictRef.setdefault(keyValue, {})
      currentLookupDictRef = nextLookupDictRef
    addEle = True
    # Check to see if this dict has already been added
    if currentLookupDictRef:
      lookedUpDict = currentLookupDictRef.get('dict', None)
      lookedUpIdx = currentLookupDictRef.get('idx', None)
      (hasSameKeyValuePairs, dictDiffErrorMsg) = checkDictsAreSame(
        dictEle, "listOfDicts["+str(idx)+"]",
        lookedUpDict, "listOfDicts["+str(lookedUpIdx)+"]" )
      if hasSameKeyValuePairs and removeExactDuplicateElements:
        # This is a 100% duplicate element to one previously added.
        # Therefore, marke this duplicate element to be removed from the
        # orginal list.
        duplicateIndexesToRemoveList.append(idx)
        addEle = False
      else:
        raise Exception(
          "Error, listOfDicts["+str(idx)+"]="+sorted_dict_str(dictEle)+" has duplicate"+\
          " values for the list of keys "+str(listOfKeys)+" with the element"+\
          " already added listOfDicts["+str(lookedUpIdx)+"]="+\
          sorted_dict_str(lookedUpDict)+" and differs by "+str(dictDiffErrorMsg)+"!")
    # Need to go back and reset the dict on the last dict in the
    # data-structure so that modifications to the dicts that are looked up
    # will modify the original list.
    if addEle:
      currentLookupDictRef.update({'dict':dictEle, 'idx':idx-numRemoved})
    else:
      numRemoved += 1
    idx += 1
  # Remove 100% duplicate elements marged above
  removeElementsFromListGivenIndexes(listOfDicts, duplicateIndexesToRemoveList)
  return  lookupDict


# Lookup a dict (and optionally also its index location) in a list of dicts
# given a lookup dict returned from createLookupDictForListOfDicts() where the
# key/value pairs match
#
# lookupDict [in]: A dict created by createLookupDictForListOfDicts() given
# the same listOfKeys used in that function.
#
# listOfKeys [in]: List of keys that was used used to create lookupDict.
#
# listOfValues [in]: A list of values for the given list of keys in
# listOfKeys.
#
# alsoReturnIdx [in]: If True, then the index of the located dict in the
# original listOfDicts will be returned as well.  (default False)
#
# If the matching dict is found, then it will be returned as:
#
#   matchingDict = lookupDictGivenLookupDict(...)
#
# If alsoReturnIdx==True, then also the index will be returned as:
#
#   (matchingDict, idx) = lookupDictGivenLookupDict(...)
#
# If the matching dict is not found, then None will be returned or the tuple
# (None, None) if alsoReturnIdx==True.
#
# NOTE: This is an implementation function that is used in the class
# SearchableListOfDicts.  Please use that class instead of this raw function.
#
def lookupDictGivenLookupDict(lookupDict, listOfKeys, listOfValues,
  alsoReturnIdx=False,
  ):
  #print("\nlookupDict = "+str(lookupDict))
  #print("\nlistOfKeys = "+str(listOfKeys))
  #print("\ndictToFind = "+str(dictToFind))
  if len(listOfKeys) != len(listOfValues):
    raise Exception("Error, len(listOfKeys)="+str(len(listOfKeys))+\
    " != len(listOfValues)="+str(len(listOfValues))+" where"+\
    " listOfKeys="+str(listOfKeys)+\
    " and listOfValues="+str(listOfValues)+"!")
  currentSubLookupDict = lookupDict
  idx = 0
  for idx in xrange(len(listOfValues)):
    key = listOfKeys[idx]
    #print("\nkey = '"+key+"'")
    keyValueToFind = listOfValues[idx]
    #print("keyValueToFind = '"+str(keyValueToFind)+"'")
    #print("currentSubLookupDict = "+str(currentSubLookupDict))
    keyValueLookedUp = currentSubLookupDict.get(keyValueToFind, None)
    #print("keyValueLookedUp = "+str(keyValueLookedUp))
    if not keyValueLookedUp:
      if alsoReturnIdx: return (None, None)
      return None
    currentSubLookupDict = keyValueLookedUp
  if keyValueLookedUp:
    if alsoReturnIdx:
      return (keyValueLookedUp.get('dict'), keyValueLookedUp.get('idx'))
    return keyValueLookedUp.get('dict')
  return None


# Class that encapsulates a list of dicts and an efficient lookup of a dict
# given a list key/value pairs to match.
#
# Once created, this object acts like a list of dicts in most cases but also
# contains functions to search for speicfic dicts given a set of key/value
# pairs.
#
# Any modifications to the dicts looked up with this object will edit the
# dicts in the underlying list of dicts.  This therefore makes this class act
# as a type of multi-key lookup dict using the member function
# lookupDictGivenKeyValuesList(['keyval0', 'keyval1', ...]).  This provides a
# handy way to access and edit the underlying dicts that require
# multi-key/value pairs to find them.
#
# NOTE: The key values for the list of keys given in listOfKeys must be
# unique!  If it is not, then an excpetion will be thrown.
#
class SearchableListOfDicts(object):

  # Constructor
  #
  # listOfDicts [stored, may be modifed]: List of dicts that a search
  # data-structure will be created for.
  #
  # listOfKeys [stored, will not be modified]: List of the names of keys in
  # the dicts of listOfDicts that a search data-structure will be created for
  # and defines the set of key/value pairs used to look up up dicts in
  # listOfDicts.
  #
  # removeExactDuplicateElements [in]: If True, then exact duplicate dicts
  # based on the key/value pairs in listOfKeys will be removed from
  # listOfDicts (which is modified in place, not a copy). (default False)
  #
  # keyMapList [in]: Optional list of key names in the input
  # keyValueDictToFind to pull out and used the match the key/value pairs in
  # the listOfKeys.  This allows a mapping from int input dict key names to
  # the output dict key names. (default None)
  #
  def __init__(self, listOfDicts, listOfKeys,
    removeExactDuplicateElements=False, keyMapList=None,
    ):
    if keyMapList:
      if len(listOfKeys) != len(keyMapList):
        raise Exception("Error, listOfKeys="+str(listOfKeys)+\
          " keyMapList="+str(listOfKeys)+" have different lenghts!" )  
    self.__listOfDicts = listOfDicts
    self.__listOfKeys = listOfKeys
    self.__keyMapList = keyMapList
    self.__lookupDict = createLookupDictForListOfDicts(
      self.__listOfDicts, self.__listOfKeys,
      removeExactDuplicateElements=removeExactDuplicateElements)

  # Convert to string rep
  def __str__(self):
    myStr = "SearchableListOfDicts{listOfDicts="+str(self.__listOfDicts)+\
      ", listOfKeys="+str(self.__listOfKeys)+", lookupDict="+str(self.__lookupDict)+"}"
    return myStr

  # Return listOfDicts passed into Constructor 
  def getListOfDicts(self):
    return self.__listOfDicts

  # Return listOfKeys passed to Constructor
  def getListOfKeys(self):
    return self.__listOfKeys

  # Return keyMapList passed to Constructor
  def getKeyMapList(self):
    return self.__keyMapList

  # Lookup a dict given a dict with same key/value pairs for keys listed in
  # listOfKeys.
  def lookupDictGivenKeyValueDict(self, keyValueDictToFind, alsoReturnIdx=False):
    if self.__keyMapList:
      keyListToUse = self.__keyMapList
    else:
      keyListToUse = self.__listOfKeys
    keyValuesListToFind = []
    for idx in xrange(len(keyListToUse)):
      keyValuesListToFind.append(keyValueDictToFind.get(keyListToUse[idx]))
    lookupRtn = self.lookupDictGivenKeyValuesList(keyValuesListToFind, alsoReturnIdx)
    return lookupRtn

  # Lookup a dict given a flat list of values for the keys
  #
  # Must be in same order self.getListOfKeys().
  #
  def lookupDictGivenKeyValuesList(self, keyValuesListToFind, alsoReturnIdx=False):
    lookupRtn = lookupDictGivenLookupDict(self.__lookupDict, self.__listOfKeys,
      keyValuesListToFind, alsoReturnIdx)
    return lookupRtn

  # Functions to allow this to act like a list
  def __len__(self):
    return len(self.__listOfDicts)
  def __getitem__(self, index_in):
    return self.__listOfDicts[index_in]


# Create a SearchableListOfDicts object for a list of builds dicts that allows
# lookups of builds given the keys "group" => "site" => "buildname" :
# build_dict.
def createSearchableListOfBuilds(buildsListOfDicts):
  return SearchableListOfDicts(buildsListOfDicts, ['group', 'site', 'buildname'])


# Create a SearchableListOfDicts object for a list of tests with issue
# trackers that allows lookups of tests given the keys "site" => "buildName"
# => "testname" : test_dict.
def createSearchableListOfTests(testsListOfDicts, removeExactDuplicateElements=False):
  return SearchableListOfDicts(testsListOfDicts, ['site', 'buildName', 'testname'],
    removeExactDuplicateElements=removeExactDuplicateElements)


# Create a SearchableListOfDicts object for a list of build dicts allows
# lookups that match the 'site' and 'buildname' fields but uses input for the
# search that are test dicts that have the fiels 'site' and 'buildName'.
def createTestToBuildSearchableListOfDicts(buildsLOD,
   removeExactDuplicateElements=False,
   ):
  return SearchableListOfDicts( buildsLOD, ('site', 'buildname'),
    removeExactDuplicateElements=removeExactDuplicateElements,
    keyMapList=('site', 'buildName') )
  # NOTE: The extra keyMapList is needed because CDash used the key name
  # 'buildname' for the build name returned form the cdash/index.php page
  # while it gave the build name the key name 'buildName' for the data
  # returned from cdash/queryTests.php.


# Match functor that returns true if the input dict has key/values that
# matches one dicts in the input SearchableListOfDicts.
class MatchDictKeysValuesFunctor(object):

  # Construct with a SearchableListOfDicts object 
  def __init__(self, searchableListOfDict):
    self.__searchableListOfDict = searchableListOfDict

  # Convert to string rep for debugging/etc.
  def __str__(self):
    myStr = "MatchDictKeysValuesFunctor{"+str(self.__searchableListOfDict)+"}"
    return myStr

  # Return 'true' if the key/value pairs in dict_in match the key/value pairs
  # in one of the dicts in the searchableListOfDict object.
  def __call__(self, dict_in):
    matchingDict = self.__searchableListOfDict.lookupDictGivenKeyValueDict(dict_in)
    if matchingDict:
      return True
    return False


# Transform functor that adds issue tracker info and URL to an existing test
# dict.
#
# This functor looks up the test based on 'site', 'buildName', and 'testname'
# keys to find the entry in the list of known issues with issue trackers and
# then it copies the issue issue tracker fields to the input/output test dict.
class AddIssueTrackerInfoToTestDictFunctor(object):

  # Construct with a SearchableListOfDicts object that has issue tracker info.
  # This object testsWithIssueTrackersSLOD must have been constructed using
  # the function createSearchableListOfTests() so it will allow lookups based
  # on the 'site', 'buildName', and 'testname' keys.
  def __init__(self, testsWithIssueTrackersSLOD, addEmptyOnNoMatch=True):
    self.__testsWithIssueTrackersSLOD = testsWithIssueTrackersSLOD
    self.__addEmptyOnNoMatch = addEmptyOnNoMatch

  # Lookup the issue tracker info and add it as new key/value pairs to
  # testDict_inout.
  def __call__(self, testDict_inout):
    # Look up the entry for the test tracker info based on the 'site',
    # 'buildName', and 'testname' key/value pairs in testDict_inout.
    matchingDict = \
      self.__testsWithIssueTrackersSLOD.lookupDictGivenKeyValueDict(testDict_inout)
    if matchingDict:
      issue_tracker = matchingDict['issue_tracker']
      issue_tracker_url = matchingDict['issue_tracker_url']
    else:
      if self.__addEmptyOnNoMatch:
        issue_tracker = ""
        issue_tracker_url = ""
      else:
        raise Exception(
         "Error, testDict_inout="+str(testDict_inout)+\
          " does not have an assigned issue tracker!")
    testDict_inout[u'issue_tracker'] = issue_tracker
    testDict_inout[u'issue_tracker_url'] = issue_tracker_url
    return testDict_inout


# Assert that the list of tests with issue trackers matches the expected
# builds.
#
# testsWithIssueTrackersLOD [in]: List of dicts of tests with issue trackers.
#   Here, only the fields 'site', 'buildName', and 'testname' are significant.
#
# expectedBuildsLOD [in]: List of dicts of expected builds with fields 'site',
# 'buildname'.  Here, the key/value pairs 'site' and 'buildname' must be
# unique.  The 'group' field is ignored (because cdash/queryTests.php does not
# give the 'group' of each test).
#
# This returns a tuple (matches, errMsg).  If all of the tests match, then
# 'matches' will be True and errMsg=="".  If one or more of the tests don't
# match then 'matches' will be False and 'errMsg' will give a message about
# which tests are missing.
#
def testsWithIssueTrackersMatchExpectedBuilds( testsWithIssueTrackersLOD,
  testToExpectedBuildsSLOD,
  ):
  # Gather up all of the tests that don't match one of the expected builds
  nonmatchingTestsWithIssueTrackersLOD = []
  for testDict in testsWithIssueTrackersLOD:
    expectedBuildDict = testToExpectedBuildsSLOD.lookupDictGivenKeyValueDict(testDict)
    if not expectedBuildDict:
      nonmatchingTestsWithIssueTrackersLOD.append(
        {'site':testDict['site'], 'buildName':testDict['buildName'],
         'testname':testDict['testname']} )
  # If all tests matched, return True
  if len(nonmatchingTestsWithIssueTrackersLOD) == 0:
    return (True, "")
  # One or more tests did not match so build an error message and return False
  errMsg = \
    "Error: The following tests with issue trackers did not match 'site' and"+\
    " 'buildName' in one of the expected builds:\n"
  for testDict in nonmatchingTestsWithIssueTrackersLOD:
    errMsg += \
      "  {'site'='"+testDict['site']+"'"+\
      ", 'buildName'="+testDict['buildName']+"'"+\
      ", 'testname'="+testDict['testname']+"'}\n"
  return (False, errMsg)


# Extract just the date from the testDict['buildstartdate'] field
def dateFromBuildStartTime(buildStartTime):
  return buildStartTime.split('T')[0]  


# Get the test history CDash cache file.
#
# Note: this takes care of things like having '/' in the test name
#
def getTestHistoryCacheFileName(date, site, buildName, testname, daysOfHistory):
  testHistoryFileName = \
    date+"-"+site+"-"+buildName+"-"+testname+"-HIST-"+str(daysOfHistory)+".json"
  return testHistoryFileName.replace('/', '_')


# Transform functor that computes and add detailed test history to an existing
# test dict so that it can be printed in the table
# createCDashTestHtmlTableStr().
#
# ToDo: Document the fields set by this functor
#
class AddTestHistoryToTestDictFunctor(object):


  # Constructor which takes additional data needed to get the test history and
  # other stuff.
  #
  # By default, this wil always read the data from the cache file if that file
  # already exists.
  #
  def __init__(self, cdashUrl, projectName, date, daysOfHistory,
    testCacheDir, useCachedCDashData=True, alwaysUseCacheFileIfExists=True,
    verbose=False, printDetails=False,
    extractCDashApiQueryData_in=extractCDashApiQueryData, # For unit testing
    ):
    self.__cdashUrl = cdashUrl
    self.__projectName = projectName
    self.__date = date
    self.__daysOfHistory = daysOfHistory
    self.__testCacheDir = testCacheDir
    self.__useCachedCDashData = useCachedCDashData
    self.__alwaysUseCacheFileIfExists = alwaysUseCacheFileIfExists
    self.__verbose = verbose
    self.__printDetails = printDetails
    self.__extractCDashApiQueryData_in = extractCDashApiQueryData_in


  # Get test history off CDash and add test history info and URL to info we
  # find out from that test history
  #
  def __call__(self, testDict):

    #pp = pprint.PrettyPrinter(indent=2)

    #print("\ntestDict:\n")
    #pp.pprint(testDict)

    # Get short names for data inside of this functor
    cdashUrl = self.__cdashUrl
    projectName = self.__projectName
    testDayDate = validateAndConvertYYYYMMDD(self.__date)
    daysOfHistory = self.__daysOfHistory

    # Get basic info about the test from the from the testDict
    site = testDict["site"]
    buildName = testDict["buildName"]
    testname = testDict["testname"]

    # Determine if this test has data from CDash or if it does not
    if testDict.get('buildstarttime', None):
      testAlreadyHasCDashData = True
    else:
      testAlreadyHasCDashData = False

    # Date range for test history
    dayAfterCurrentTestDay = \
      (testDayDate+datetime.timedelta(days=1)).isoformat()
    daysBeforeCurrentTestDay = \
      (testDayDate+datetime.timedelta(days=-1*daysOfHistory+1)).isoformat()

    # Define queryTests.php query filters for test history
    testHistoryQueryFilters = \
      "filtercombine=and&filtercombine=&filtercount=5&showfilters=1&filtercombine=and"+\
      "&field1=buildname&compare1=61&value1="+buildName+\
      "&field2=testname&compare2=61&value2="+testname+\
      "&field3=site&compare3=61&value3="+site+\
      "&field4=buildstarttime&compare4=84&value4="+dayAfterCurrentTestDay+\
      "&field5=buildstarttime&compare5=83&value5="+daysBeforeCurrentTestDay
    
    # URL used to get the history of the test in JSON form
    testHistoryQueryUrl = \
      getCDashQueryTestsQueryUrl(cdashUrl, projectName, None, testHistoryQueryFilters)

    # URL to imbed in email to show the history of the test to humans
    testHistoryBrowserUrl = \
      getCDashQueryTestsBrowserUrl(cdashUrl, projectName, None, testHistoryQueryFilters)

    # URL for to the build summary on index.php page
    buildHistoryEmailUrl = getCDashIndexBrowserUrl(
      cdashUrl, projectName, None,
      "filtercombine=and&filtercombine=&filtercount=4&showfilters=1&filtercombine=and"+\
      "&field1=buildname&compare1=61&value1="+buildName+\
      "&field2=site&compare2=61&value2="+site+\
      "&field3=buildstarttime&compare3=84&value3="+dayAfterCurrentTestDay+\
      "&field4=buildstarttime&compare4=83&value4="+daysBeforeCurrentTestDay )
    # ToDo: Replace this with the the URL to just this one build the index.php
    # page.  To do that, get the build stamp from the list of builds on CDash
    # and then create a URL link for this one build given 'site', 'buildName',
    # and 'buildStamp'.  (NOTE: We can't use 'buildstarttime' without
    # replacing ':' with '%' or the URL will not work with CDash.)

    # Set the names of the cached files so we can check if they exists and
    # write them out otherwise
    testHistoryCacheFileFullName = \
      getTestHistoryCacheFileName(self.__date,site,buildName,testname,daysOfHistory)
    # Possibly compress the file name if it is too long
    testHistoryCacheFilePath = \
     self.__testCacheDir+"/"+\
      getCompressedFileNameIfTooLong(testHistoryCacheFileFullName,self.__date+"-","json")

    if self.__verbose:
      gettingTestHistoryMsg = \
        "Getting "+str(daysOfHistory)+" days of history for "+testname+\
        " in the build "+buildName+" on "+site
      if os.path.exists(testHistoryCacheFilePath):
        gettingTestHistoryMsg += " from cache file"
      else:
        gettingTestHistoryMsg += " from CDash"
      print(gettingTestHistoryMsg)

    # Get the test history off of CDash (or from reading the cache file)
    testHistoryLOD = downloadTestsOffCDashQueryTestsAndFlatten(
      testHistoryQueryUrl, testHistoryCacheFilePath,
      useCachedCDashData=self.__useCachedCDashData,
      alwaysUseCacheFileIfExists=self.__alwaysUseCacheFileIfExists,
      verbose=self.__printDetails,
      extractCDashApiQueryData_in=self.__extractCDashApiQueryData_in
      )

    # Sort the list with the most recent day first
    testHistoryLOD.sort(reverse=True, key=DictSortFunctor(['buildstarttime']))

    # ToDo: Put in check that testDict['buildstarttime'] equals the most
    # recent test in testHistoryLOD.  That is needed to ensure that we got the
    # date dayAfterCurrentTestDay correct!  Actually, that is only going to be
    # true for tests that did not run in the current testing day.  For missing
    # tests, the current testing day results will be missing.

    # Gather up number of nopass days (already in order)
    nopassDatesList=[]
    for testHistoryDict in testHistoryLOD:
      if not isTestPassed(testHistoryDict):
        nopassDatesList.append(dateFromBuildStartTime(testHistoryDict['buildstarttime']))

    # Set most recent and previous failure dates
    if len(nopassDatesList) == 0:
      mostRecentNopassDate="None"
      previousNopassDate="None"
    elif len(nopassDatesList) == 1:
      mostRecentNopassDate=nopassDatesList[0]
      previousNopassDate="None"
    else:
      mostRecentNopassDate=nopassDatesList[0]
      previousNopassDate=nopassDatesList[1]

    # ToDo: Replace above with function to sort testHistoryLOD by
    # 'buildstarttime' with the most recent test/build at the top and get the
    # test history stats like 'numPassDays', 'numNotRunDays', 'numFailDays',
    # 'mostRecentNopassTestIndex' (before today), 'mostRecentPassTestIndex'
    # (before today), 'numConsecPassDays' (starting from most recent pass day,
    # including today) and 'numConsecNopassDays' (starting from most recent
    # nopass day, including today).  This will make it easy to get other
    # various statistics and other data out of this test history as shown
    # below.

    # Fill in the test details for the current day test from the test top
    # history dict if it ran today.
    if not testAlreadyHasCDashData:
      # Determine if there is any test history at all and if there is, get the
      # top date
      hasDataForCurrentDate = False
      if testHistoryLOD:
        mostRecentTestHistoryDate = \
          dateFromBuildStartTime(testHistoryLOD[0]['buildstarttime'])
        if mostRecentTestHistoryDate == self.__date:
          # The test ran.  Therefore, just grab the info for the test
          testDict.update(testHistoryLOD[0])
          hasDataForCurrentDate = True
      # If there is no history for the current day, then the test is missing
      if not hasDataForCurrentDate:
        # The test did not run in the current testing day so don't add any
        # info for the current testing day beyond the minimum to dispaly in
        # the table
        testDict['status'] = "Missing"
        testDict['details'] = "Missing"

    # ToDo: Lookup the matching build info so that we can get the buildstamp
    # in order to build a good link to the build on CDash?

    # Get the link to the test details if it exists
    testDetailsLink = testDict.get('testDetailsLink', None)
    if testDetailsLink:
      fullTestDetailsLink = cdashUrl+"/"+testDetailsLink
    else:
      fullTestDetailsLink = None

    # Assign all of the new test dict fields that need to be added
    testDict["site_url"] = ""
    testDict['buildName_url'] = buildHistoryEmailUrl # ToDo: Change to one build
    if fullTestDetailsLink:
      testDict['testname_url'] = fullTestDetailsLink
      testDict['status_url'] = fullTestDetailsLink
    testDict['test_history_num_days'] = daysOfHistory
    testDict['test_history_query_url'] = testHistoryQueryUrl
    testDict['test_history_browser_url'] = testHistoryBrowserUrl
    testDict['test_history_list'] = testHistoryLOD
    testDict['nopass_last_x_days'] = len(nopassDatesList)
    testDict['nopass_last_x_days_url'] = testHistoryBrowserUrl
    testDict['most_recent_nopass_date'] = mostRecentNopassDate
    testDict['previous_nopass_date'] = previousNopassDate
    #testDict['previous_nopass_date_url'] = ""  # ToDo: Put in link to this build

    # Return the updated test dict with the new fields
    return testDict


# Gather up a list of the missing builds.
#
# Inputs:
#
#   buildLookupDict [in]: Lookup dict of build summary dicts gotten off CDash
#   
#   expectedBuildsList [in]: List of expected builds dict with fields 'group',
#   'site', and 'buildname'.
#
# Returns an array of dicts of missing expected builds with list elements:
#
#    {'group':"???", 'site':"???", 'buildname':"???", 'status':"???", ...}
#
# wher the '...' will be the rest of the fields for builds that exist on CDash
# but don't have full results.
#
# The field 'status' will either be given either:
#
#   "Build not found on CDash"
#
# or
#
#   "Build exists but no test results"
#
# ToDo: Change name of 'status' to 'build_missing_status' and add other
# 'build_missing_status' values like:
#
#   "Build exists but no build results"
#   "Build exists but no configure results"
#
def getMissingExpectedBuildsList(buildsSearchableListOfDicts, expectedBuildsList):
  missingExpectedBuildsList = []
  for expectedBuildDict in expectedBuildsList:
    #print("\nexpectedBuildDict = "+str(expectedBuildDict))
    buildSummaryDict = \
      buildsSearchableListOfDicts.lookupDictGivenKeyValueDict(expectedBuildDict)
    #print("buildSummaryDict = "+str(buildSummaryDict))
    if not buildSummaryDict:
      # Expected build not found!
      missingExpectedBuildDict = copy.deepcopy(expectedBuildDict)
      missingExpectedBuildDict.update({'status':"Build not found on CDash"})
      #print("missingExpectedBuildDict = "+str(missingExpectedBuildDict))
      missingExpectedBuildsList.append(missingExpectedBuildDict)
    elif not buildSummaryDict.get('test', None):
      # Build exists but it is missing tests!
      missingExpectedBuildDict = copy.deepcopy(expectedBuildDict)
      missingExpectedBuildDict.update({'status':"Build exists but no test results"})
      #print("missingExpectedBuildDict = "+str(missingExpectedBuildDict))
      missingExpectedBuildsList.append(missingExpectedBuildDict)
    else:
      # This build exists and it has test results so don't add it
      None
  # Return the list of missing expected builds and status
  return missingExpectedBuildsList


# Download set of builds from CDash builds and return flattened list of dicts
#
# The cdash/api/v1/index.php query selecting the set of builds is provided by
# cdashIndexBuildsQueryUrl.
#
# If cdashIndexBuildsQueryCacheFile != None, then the raw JSON data-structure
# downloaded from CDash will be written to the file
# cdashIndexBuildsQueryCacheFile or read from that file if
# useCachedCDashData==True.
#
# If alwaysUseCacheFileIfExists==True, then if the file
# cdashIndexBuildsQueryCacheFile already exists, it will always be read to get
# data instead of communicating with CDash even if useCachedCDashData==False.
# 
# The list of builds pulled off of CDash is flattended and extracted using the
# function flattenCDashIndexBuildsToListOfDicts().
#
# NOTE: The optional argument extractCDashApiQueryData_in is used in unit
# testing to avoid calling CDash.
#
def downloadBuildsOffCDashAndFlatten(
  cdashIndexBuildsQueryUrl,
  fullCDashIndexBuildsJsonCacheFile=None,
  useCachedCDashData=False,
  alwaysUseCacheFileIfExists = False,
  verbose=True,
  extractCDashApiQueryData_in=extractCDashApiQueryData,
  ):
  # Get the query data
  fullCDashIndexBuildsJson = getAndCacheCDashQueryDataOrReadFromCache(
    cdashIndexBuildsQueryUrl, fullCDashIndexBuildsJsonCacheFile, useCachedCDashData,
    alwaysUseCacheFileIfExists, verbose=verbose,
    extractCDashApiQueryData_in=extractCDashApiQueryData_in )
  # Get trimmed down set of builds
  buildsListOfDicts = \
    flattenCDashIndexBuildsToListOfDicts(fullCDashIndexBuildsJson)
  return buildsListOfDicts


# Download set of tests from cdash/api/v1/ctest/queryTests.php and return
# flattened list of dicts
#
# cdashQueryTestsUrl [in]: String URL for cdash/api/v1/ctest/queryTests.php
# with filters.
#
# If verbose==True, the the CDash query URL will be printed to STDOUT.
# Otherwise, this function is silent and will not return any output to STDOUT.
#
# If fullCDashQueryTestsJsonCacheFile != None, then the raw JSON
# data-structure will be written to that file.
#
# If useCachedCDashData==True, then data will not be pulled off of CDash and
# instead the list of builds will be read from the file cdashQueryCacheFile
# which must already exist from a prior call to this function (mostly for
# debugging and unit testing purposes).
#
# If alwaysUseCacheFileIfExists==True, then if the file
# cdashIndexBuildsQueryCacheFile already exists, it will always be read to get
# data instead of communicating with CDash even if useCachedCDashData==False.
# 
# The list of tests pulled off CDash is flattended and returned by the
# function flattenCDashQueryTestsToListOfDicts().
#
# NOTE: The optional argument extractCDashApiQueryData_in is used in unit
# testing to avoid calling CDash.
#
def downloadTestsOffCDashQueryTestsAndFlatten(
  cdashQueryTestsUrl,
  fullCDashQueryTestsJsonCacheFile=None,
  useCachedCDashData=False,
  alwaysUseCacheFileIfExists = False,
  verbose=True,
  extractCDashApiQueryData_in=extractCDashApiQueryData,
  ):
  # Get the query data
  fullCDashQueryTestsJson = getAndCacheCDashQueryDataOrReadFromCache(
    cdashQueryTestsUrl, fullCDashQueryTestsJsonCacheFile, useCachedCDashData,
    alwaysUseCacheFileIfExists, verbose=verbose,
    extractCDashApiQueryData_in=extractCDashApiQueryData_in )
  # Get flattend set of tests
  testsListOfDicts = \
    flattenCDashQueryTestsToListOfDicts(fullCDashQueryTestsJson)
  return testsListOfDicts


# Returns True if a build has configure failures
def buildHasConfigureFailures(buildDict):
  configureDict = buildDict.get('configure', None)
  if configureDict and configureDict['error'] > 0:
    return True
  return False


# Returns True if a build has compilation/build failures
def buildHasBuildFailures(buildDict):
  compilationDict = buildDict.get('compilation', None)
  if compilationDict and compilationDict['error'] > 0:
    return True
  return False


# Returns True if a test has 'status' 'Passed'
def isTestPassed(testDict):
  return (testDict.get('status', None) == 'Passed')


# Returns True if a test has 'status' 'Failed'
def isTestFailed(testDict):
  return (testDict.get('status', None) == 'Failed')


# Returns True if a test has 'status' 'Not Run'
def isTestNotRun(testDict):
  return (testDict.get('status', None) == 'Not Run')


# Functor class to sort a row of dicts by multiple columns of string data.
class DictSortFunctor(object):
  def __init__(self, sortKeyList):
    self.sortKeyList = sortKeyList
  def __call__(self, dict_in):
    sortKeyStr=""
    for key in self.sortKeyList:
      keyData = dict_in.get(key)
      if sortKeyStr:
        sortKeyStr += "-"+str(keyData)
      else:
        sortKeyStr = keyData
    return sortKeyStr


# Sort and limit a list of dicts
#
# Arguments:
#
# listOfDicts [in]: List of dicts that will be sorted according to keys.
#
# sortKeyList [in]: List of dict keys that define the sort order for the data
# in the list.  The default is None which means that no sort is performed.
#
# limitRowsToDisplay [in]: The max number of rows to display.  The default is
# None which will result in no limit to the number of rows displayed.  The top
# limitRowsToDisplay items will be dispalyed after the list is sorted.
#
def sortAndLimitListOfDicts(listOfDicts, sortKeyList = None,
  limitRowsToDisplay = None\
  ):
  # Sort the list
  if sortKeyList:
    listOfDictsOrdered = copy.copy(listOfDicts)  # Shallow copy
    listOfDictsOrdered.sort(key=DictSortFunctor(sortKeyList))
  else:
    listOfDictsOrdered = listOfDicts  # No sort being done
  # Limit rows
  if limitRowsToDisplay == None:
    listOfDictsLimited = listOfDictsOrdered
  else:
    listOfDictsLimited = listOfDictsOrdered[0:limitRowsToDisplay]
  # Return the final sorted limited list
  return listOfDictsLimited


# Class to store dict key and table header
class TableColumnData(object):
  validColAlignList=["left","right","center","justify","char"]
  def __init__(self, dictKey, colHeader, colAlign="left"):
    self.dictKey = dictKey
    self.colHeader = colHeader
    if not colAlign in self.validColAlignList:
      raise Excpetion(
        "Error, colAlign="+colAlign+" not valid.  Please choose from"+\
        " the list ['" + "', '".join(validColAlignList) + "']!" )
    self.colAlign = colAlign


# Create an html table string from a list of dicts and column headers.
#
# Arguments:
#
# tableTitle [in]: String for the name of the table included at the top of the
# table.
# 
# colDataList [in]: List of TableColumnData objects where
#   colDataList[j].dictKey gives the name of the key for that column of data,
#   colDataList[j].colHeader is the text name for the column header and
#   colDataList[j].colAlign gives the HTML alignment.  That columns in the
#   table will listed in the order given in this list.
#
# rowDataList [in]: List of dicts that provide the data from the table.  The
#   dict in each row must have the keys specified by colData[j].dictKey.  In
#   addition, if (key_url=rowDataList[i].get(colData[j].dictKey+"_url",#
#   None))!=None, then the table entry will be an HTML link <a
#   href="dataRowList[i].get(key_url)">dataRowList[i].get(key)</a>.
#
# htmlStyle [in]: The HTML style data (between <style></style>.  If None is
# passed in then a default style is provided internally.
#
# htmlTableStyle [in]: The style for the HTML table used in <table
#   style=htmlTableStyle>.  If set to None, then a default style is used.  To
#   not set a style, pass in the empty string "" (not None).
#
def createHtmlTableStr(tableTitle, colDataList, rowDataList,
  htmlStyle=None, htmlTableStyle=None \
  ):

  # style options for the table
  defaultHtmlStyle=\
    "table, th, td {\n"+\
    "  padding: 5px;\n"+\
    "  border: 1px solid black;\n"+\
    "  border-collapse: collapse;\n"+\
    "}\n"+\
    "tr:nth-child(even) {background-color: #eee;}\n"+\
    "tr:nth-child(odd) {background-color: #fff;}\n"
  if htmlStyle != None: htmlStyleUsed = htmlStyle
  else: htmlStyleUsed = defaultHtmlStyle
  htmlStr="<style>"+htmlStyleUsed+"</style>\n"

  # Table title and <table style=...>
  htmlStr+="<h3>"+tableTitle+"</h3>\n"
  if htmlTableStyle != None: htmlTableStyleUsed = htmlTableStyle
  else: htmlTableStyleUsed = "style=\"width:100%\""
  htmlStr+="<table "+htmlTableStyleUsed+">\n\n"

  # Column headings:
  htmlStr+="<tr>\n"
  for colData in colDataList:
    htmlStr+="<th>"+colData.colHeader+"</th>\n"
  htmlStr+="</tr>\n\n"

  # Rows for the table
  row_i = 0
  for rowData in rowDataList:
    #print("\nrowData = "+str(rowData))
    htmlStr+="<tr>\n"
    for colData in colDataList:
      dictKey = colData.dictKey
      #print("\ndictKey = "+dictKey)
      # Get the raw entry for this column
      entry = rowData.get(dictKey, None)
      if entry == None:
        raise Exception(
          "Error, column dict ='"+colData.dictKey+"' row "+str(row_i)+\
          " entry is 'None' which is not allowed! row dict = "+str(rowData))  
      # See if the _url key also exists
      dictKey_url = dictKey+"_url"
      #print("dictKey_url = "+dictKey_url)
      entry_url = rowData.get(dictKey_url, None)
      #print("entry_url = "+str(entry_url))
      # Set the text for this row/column entry with or without the hyperlink
      if entry_url:
        entryStr = "<a href=\""+entry_url+"\">"+str(entry)+"</a>"
      else:
        entryStr = entry
      #print("entryStr = "+entryStr)
      # Set the row entry in the HTML table
      htmlStr+=\
        "<td align=\""+colData.colAlign+"\">"+\
        str(entryStr).strip()+\
        "</td>\n"
    htmlStr+="</tr>\n\n"
    row_i += 1

  # End of table
  htmlStr+="</table>\n\n"  # Use two newlines makes for good formatting!
  return(htmlStr)


# Get string for table title for CDash data to display
#
# Arguments:
#
# Arguments:
#
# dataTitle [in]: Name of the data category.
#
# dataCountAcronym [in]: Acronym for the type of data being displayed
# (e.g. 'twoi' for "Tests With Out issue trackers").  This is printed in the
# table title in the form dataCoutAcronym=len(rowDataList).
#
# numItems [in]: The number of items of data
#
def getCDashDataSummaryHtmlTableTitleStr(dataTitle, dataCountAcronym, numItems,
  limitRowsToDisplay=None,
  ):
  tableTitle = dataTitle
  if limitRowsToDisplay:
    tableTitle += " (limited to "+str(limitRowsToDisplay)+")"
  tableTitle += ": "+dataCountAcronym+"="+str(numItems)
  return tableTitle


# Create an html table string for CDash summary data.
#
# Arguments:
#
# dataTitle [in]: Name of the data that we be included in the table title.
#
# dataCountAcronym [in]: Acronym for the type of data being displayed
# (e.g. 'twoi' for "Tests With Out issue trackers").  This is printed in the
# table title in the form dataCoutAcronym=len(rowDataList).
#
# colDataList [in]: List of TableColumnData objects where
#   colDataList[j].dictKey gives the name of the key for that column of data,
#   colDataList[j].colHeader is the text name for the column header and
#   colDataList[j].colAlign gives the HTML alignment.  That columns in the
#   table will listed in the order given in this list.
#
# rowDataList [in]: List of dicts that provide the data from the table.  The
#   dict in each row must have the keys specified by colData[j].dictKey.
#
# sortKeyList [in]: List of dict keys that define the sort order for the data
# in the list.  The default is None which means that no sort is performed.
#
# limitRowsToDisplay [in]: The max number of rows to display.  The default is
# None which will result in no limit to the number of rows displayed.  The top
# limitRowsToDisplay items will be dispalyed after the list is sorted.
#
# htmlStyle [in]: The HTML style data (between <style></style>.  If None is
# passed in then a default style is provided internally (see
# createHtmlTableStr().
#
# htmlTableStyle [in]: The style for the HTML table used in <table
#   style=htmlTableStyle>.  The default is None in which case a default is
#   picked by createHtmlTableStr(().
#
# NOTE: If len(rowDataList) == 0, then the empty string "" is returned.
#
def createCDashDataSummaryHtmlTableStr( dataTitle, dataCountAcronym,
  colDataList, rowDataList, sortKeyList=None, limitRowsToDisplay=None,
  htmlStyle=None, htmlTableStyle=None,
  ):
  # If no rows, don't create a table
  if len(rowDataList) == 0:
    return ""
  # Sort the list and limit the list
  rowDataListDisplayed = sortAndLimitListOfDicts(
    rowDataList, sortKeyList, limitRowsToDisplay)
  # Table title
  tableTitle = getCDashDataSummaryHtmlTableTitleStr(
    dataTitle, dataCountAcronym, len(rowDataList), limitRowsToDisplay )
  # Create and return the table
  return createHtmlTableStr( tableTitle,
    colDataList, rowDataListDisplayed, htmlStyle, htmlTableStyle )


# Create a tests HTML table string
#
# testTypeDescr [in]: Description of the test type being tabulated
# (e.g. "Failing tests without issue trackers")
#
# testTypeCountAcronym [in]: Acronym for the test type being tabulated
# (e.g. "twoif")
#
# testTypeCountNum [in]: Number of total items for the test type, before
# limiting (e.g. 25)
#
# testsLOD [in]: List of dicts of the test data typically first first
# downloaded from CDash.  Each dict in this list must also have been operated
# on by the functors AddIssueTrackerInfoToTestDictFunctor and
# AddTestHistoryToTestDictFunctor in order to have all of the data needed to
# print in this table.
#
# daysOfHistory [in]: Number of days of test history being displayed.  This is
# needed for one of the table column headers.  (ToDo: Remove this and get this
# from the data).
#
# limitRowsToDisplay [in]: Limit of the number of rows to display.  If this
# limited then this arugment is needed in order to print "(limited it ???)" in
# the table title.  Should be 'None' if this listing is not limited. (default
# None)
#
# htmlStyle [in]: HTML sytle for the entire table (see createHtmlTableStr())
# (default None)
#
# htmlTableStyle [in]: Sytle inside of <table ... > (see createHtmlTableStr())
# (default None)
#
def createCDashTestHtmlTableStr( testTypeDescr,
  testTypeCountAcronym, testTypeCountNum,
  testsLOD, daysOfHistory, limitRowsToDisplay=None,
  htmlStyle=None, htmlTableStyle=None,
  ):
  # Return empty string if no tests
  if len(testsLOD) == 0:
     return ""
  # Table title
  tableTitle = getCDashDataSummaryHtmlTableTitleStr(
    testTypeDescr, testTypeCountAcronym, testTypeCountNum, limitRowsToDisplay )
  # Create column headers
  tcd = TableColumnData
  testsColDataList = [
    tcd("site", "Site"),
    tcd("buildName", "Build Name"),
    tcd("testname", "Test Name"),
    tcd("status", "Status"),
    tcd("details", "Details"),
    tcd('nopass_last_x_days', "Nopass last "+str(daysOfHistory)+" Days", "right"),
    tcd("previous_nopass_date", "Previous Nopass Date", "right"),
    tcd("issue_tracker", "Tracker", "right"),
    ]
  # Return the HTML table
  return createHtmlTableStr( tableTitle,
    testsColDataList, testsLOD,
    htmlStyle=htmlStyle, htmlTableStyle=htmlTableStyle )


########################################################################
#
# Joe's CDash test test query and analysis code
#
# ToDo: Once under some basic testing, refactor to reduce duplication and
# improve consistency.
#
########################################################################


## This will return a dictionary with information about all the tests that were returned
## in the json from cdash as a result of the CDash query from the given inputs
#def getTestsJsonFromCdash(cdashUrl, projectName, filterFields, options,
#  verbose=False \
#  ):
#
#  cacheFolder=options.cdashQueriesCacheDir+"/test_history"
#  cacheFile=options.date+"-All-Failing-Tests.json"
#  simplified_dict_of_tests={}
#  if options.useCachedCDashData:
#    simplified_dict_of_tests=getJsonDataFromCache(cacheFolder, cacheFile)
#  
#  if not simplified_dict_of_tests and (not options.useCachedCDashData):
#    raw_json_from_cdash=getRawJsonFromCdash(cdashUrl, projectName, filterFields,
#      options, verbose)
#    simplified_dict_of_tests=getTestDictionaryFromCdashJson(raw_json_from_cdash, options)
#    if options.cdashQueriesCacheDir:
#      writeJsonDataToCache(cacheFolder, cacheFile, simplified_dict_of_tests)
#
#  getHistoricalDataForTests(simplified_dict_of_tests, cdashUrl, projectName,
#    filterFields, options)
#  return simplified_dict_of_tests
#
#
## Construct a URL and return the raw json from cdash
#def getRawJsonFromCdash(cdashUrl, projectName, filterFields, options,
#  verbose=False \
#  ):
#  # construct the cdash query.  the "/api/v1/" will cause CDash to return a json data 
#  # structure instead of a web page
#  CdashTestsApiQueryUrl= \
#    cdashUrl+ \
#    "/api/v1/queryTests.php?"+ \
#    "project="+projectName+ \
#    "&date="+options.date+ \
#    "&"+filterFields
#
#  if verbose:
#    print("Getting bulid data from:\n\n  " + CdashTestsApiQueryUrl )
#    
#  # get the json from CDash using the query constructed above
#  json_from_cdash_query=extractCDashApiQueryData(CdashTestsApiQueryUrl)
#  return json_from_cdash_query
#
#
#def getTestDictionaryFromCdashJson(CDash_json, options):
# 
#  simplified_dict_of_tests={}
#
#  # The CDash json has a lot of information and is many levels deep.  This will collect 
#  # relevant data about the tests and store it in a dictionary
#  for i in range(0, len(CDash_json["builds"])):
#
#    site=CDash_json["builds"][i]["site"]
#    build_name=CDash_json["builds"][i]["buildName"]
#    test_name=CDash_json["builds"][i]["testname"]
##    test_name_url=CDash_json["builds"][i]["testname"] 
#    days_of_history=int(options.testHistoryDays)
#    
#    
#    # A unique test is determined by the build name, the test name, and the site where it was run
#    # construct a dictionary key unique to each test using those 3 things. And initialize dictionary
#    dict_key=build_name+"---"+test_name+"---"+site
#    if dict_key in simplified_dict_of_tests:
#      simplified_dict_of_tests[dict_key]["count"]+=1
#    else:
#      simplified_dict_of_tests[dict_key]={}
#
#      # Store relevant information in the dictionary.  This information is all available from the 
#      # first CDash query we ran above.  There is only information about the given day no history
#      # some of these are just initialized but not used yet
#      simplified_dict_of_tests[dict_key]["site"]=site
#      simplified_dict_of_tests[dict_key]["build_name"]=build_name
#      simplified_dict_of_tests[dict_key]["test_name"]=test_name
#      simplified_dict_of_tests[dict_key]["test_name_url"]=options.cdashSiteUrl+"/"+CDash_json["builds"][i]["testDetailsLink"]
#      simplified_dict_of_tests[dict_key]["issue_tracker"]=""
#      simplified_dict_of_tests[dict_key]["issue_tracker_url"]=""
#      simplified_dict_of_tests[dict_key]["details"]=CDash_json["builds"][i]["details"].strip()
#      simplified_dict_of_tests[dict_key]["status"]=CDash_json["builds"][i]["status"].strip()
#      simplified_dict_of_tests[dict_key]["status_url"]=options.cdashSiteUrl+"/"+CDash_json["builds"][i]["testDetailsLink"]
#      simplified_dict_of_tests[dict_key]["count"]=1
#
#  return simplified_dict_of_tests
#
#
#def getHistoricalDataForTests(testDictionary, cdashUrl, projectName, filterFields, options):
#      # Some of the information needed is historical.  For this we need to look at the history of the test
#  for dict_key in testDictionary:
#    site=testDictionary[dict_key]["site"]
#    build_name=testDictionary[dict_key]["build_name"]
#    test_name=testDictionary[dict_key]["test_name"]
#    days_of_history=int(options.testHistoryDays)
#    given_date=validateAndConvertYYYYMMDD(options.date)
#
#    history_title_string="failures_in_last_"+str(options.testHistoryDays)+"_days"
#    
#    #URL used to get the history of the test in JSON form
#    testHistoryQueryUrl= \
#    cdashUrl+ \
#    "/api/v1/queryTests.php?"+ \
#    "project="+projectName+ \
#    "&filtercombine=and&filtercombine=&filtercount=5&showfilters=1&filtercombine=and"+ \
#    "&field1=buildname&compare1=61&value1="+build_name+ \
#    "&field2=testname&compare2=61&value2="+test_name+ \
#    "&field3=site&compare3=61&value3="+site+ \
#    "&field4=buildstarttime&compare4=84&value4="+(given_date+datetime.timedelta(days=1)).isoformat()+ \
#    "&field5=buildstarttime&compare5=83&value5="+(given_date+datetime.timedelta(days=-1*days_of_history+1)).isoformat()
#
#    #URL to imbed in email to show the history of the test to humans
#    testHistoryEmailUrl= \
#    cdashUrl+ \
#    "/queryTests.php?"+ \
#    "project="+projectName+ \
#    "&filtercombine=and&filtercombine=&filtercount=5&showfilters=1&filtercombine=and"+ \
#    "&field1=buildname&compare1=61&value1="+build_name+ \
#    "&field2=testname&compare2=61&value2="+test_name+ \
#    "&field3=site&compare3=61&value3="+site+ \
#    "&field4=buildstarttime&compare4=84&value4="+(given_date+datetime.timedelta(days=1)).isoformat()+ \
#    "&field5=buildstarttime&compare5=83&value5="+(given_date+datetime.timedelta(days=-1*days_of_history+1)).isoformat()
#
#    #URL to imbed in email to show the history of the build to humans
#    buildHistoryEmailUrl= \
#    cdashUrl+ \
#    "/index.php?"+ \
#    "project="+projectName+ \
#    "&filtercombine=and&filtercombine=&filtercount=4&showfilters=1&filtercombine=and"+ \
#    "&field1=buildname&compare1=61&value1="+build_name+ \
#    "&field2=site&compare2=61&value2="+site+ \
#    "&field3=buildstarttime&compare3=84&value3="+(given_date+datetime.timedelta(days=1)).isoformat()+ \
#    "&field4=buildstarttime&compare4=83&value4="+(given_date+datetime.timedelta(days=-1*days_of_history+1)).isoformat()                    
#
#    testDictionary[dict_key]["site_url"]=""
#    testDictionary[dict_key]["build_name_url"]=buildHistoryEmailUrl
#    testDictionary[dict_key]["test_history"]="Test History"
#    testDictionary[dict_key]["test_history_url"]=testHistoryQueryUrl
#    testDictionary[dict_key]["previous_failure_date"]=""
#    testDictionary[dict_key]["most_recent_failure_date"]=""
#    testDictionary[dict_key][history_title_string]=""
#    testDictionary[dict_key][history_title_string+"_url"]=testHistoryEmailUrl
#    testDictionary[dict_key]["count"]=1
#
#    # set the names of the cached files so we can check if they exists and write them out otherwise
#    cacheFolder=options.cdashQueriesCacheDir+"/test_history"
#    cacheFile=options.date+"-"+site+"-"+build_name+"-"+test_name+"-HIST-"+str(days_of_history)+".json"
#
#    # initialize test_history_json to empty dict.  if it is read from the cache then it will not be empty
#    # after these ifs
#    test_history_json={}
#    if options.useCachedCDashData:
#      test_history_json=getJsonDataFromCache(cacheFolder, cacheFile)
#
#    # if test_history_json is still empty then either it was not found in the cache or the user 
#    # told us not to look in the cache.  Get the json from CDash
#    if not test_history_json:
#      print("Getting "+str(days_of_history)+" days of history for "+test_name+" in the build "+build_name+" on "+site+" from CDash")
#      test_history_json=extractCDashApiQueryData(testHistoryQueryUrl)      
#
#      # cache json files if the option is on (turned on by default)
#      if options.cdashQueriesCacheDir:
#        writeJsonDataToCache(cacheFolder, cacheFile, test_history_json)
#
#    # adding up number of failures and collecting dates of the failures
#    failed_dates=[]
#    for cdash_build in test_history_json["builds"]:
#      if cdash_build["status"] != "Passed":
#        failed_dates.append(cdash_build["buildstarttime"].split('T')[0])
#
#    testDictionary[dict_key][history_title_string]=len(failed_dates)
#
#    # set most recent and previous failure dates
#    failed_dates.sort(reverse=True)
#    if len(failed_dates) == 0:
#      testDictionary[dict_key]["previous_failure_date"]="None"
#      testDictionary[dict_key]["most_recent_failure_date"]="None"
#    elif len(failed_dates) == 1:
#      testDictionary[dict_key]["previous_failure_date"]="None"
#      testDictionary[dict_key]["most_recent_failure_date"]=failed_dates[0]
#    else:
#      testDictionary[dict_key]["previous_failure_date"]=failed_dates[1]
#      testDictionary[dict_key]["most_recent_failure_date"]=failed_dates[0]
#
#
#def getJsonDataFromCache(cacheFolder, cacheFile):
#  # will read json data from specified file and return that data.
#  # if the file does not exist then return empy dict
#
#  cacheFilePath=cacheFolder+"/"+cacheFile
#  jsonData={}
#  if os.path.exists(cacheFilePath):
#    print("Reading cache file: "+cacheFilePath)
#    f = open(cacheFilePath, "r")
#    jsonData=json.load(f)
#    f.close
#  else:
#    print("Cache file: "+cacheFilePath+" not found")
#  return jsonData
#
#
#def writeJsonDataToCache(cacheFolder, cacheFile, jsonData):
#  # creating the cache directory if it does not already exist
#  if not os.path.exists(os.path.dirname(cacheFolder+"/")):
#    os.makedirs(os.path.dirname(cacheFolder+"/"))
#
#  f = open(cacheFolder+"/"+cacheFile, "w")
#  json.dump(jsonData, f)
#  f.close
#
#
#def filterDictionary(dictOfTests, fieldToTest, testValue="", testType=""):
#  dict_of_tests_that_pass={}
#  dict_of_tests_that_fail={}
#  
#  for key in dictOfTests:
#    if dictOfTests[key][fieldToTest] == "":
#      dict_of_tests_that_pass[key] = dictOfTests[key]
#    else:
#      dict_of_tests_that_fail[key] = dictOfTests[key]
#
#  return dict_of_tests_that_pass, dict_of_tests_that_fail
#
#
#def checkForIssueTracker(dictOfTests, issueTrackerDBFileName):
#  
#  dict_of_known_issues={}
#  with open(issueTrackerDBFileName, "r") as f:
#    for line in f:
#      site=line.split(",")[0].strip()
#      build_name=line.split(",")[1].strip()
#      test_name=line.split(",")[2].strip()
#      dict_key=build_name+"---"+test_name+"---"+site
#      dict_of_known_issues[dict_key]={}
#      dict_of_known_issues[dict_key]["issue_tracker_url"]=line.split(",")[3].strip()
#      dict_of_known_issues[dict_key]["issue_tracker"]=line.split(",")[4].strip()
#
#    f.close()
#  
#  for key in dictOfTests:
#    if key in dict_of_known_issues:
#      dictOfTests[key]["issue_tracker"]=dict_of_known_issues[key]["issue_tracker"]
#      dictOfTests[key]["issue_tracker_url"]=dict_of_known_issues[key]["issue_tracker_url"]
#  f.close()


#
# Create an HTML MIME Email
#  

import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate


# Create MINE formatted email object (but don't send it)
#
def createHtmlMimeEmail(fromAddress, toAddress, subject, textBody, htmlBody):

  # Create message container - the correct MIME type is multipart/alternative.
  msg = MIMEMultipart('alternative')
  msg['From'] = fromAddress
  msg['To'] = toAddress
  msg['Date'] = formatdate(localtime=True)
  msg['Subject'] = subject

  # Record the MIME types of both parts - text/plain and text/html.
  part1 = MIMEText(textBody, 'plain')
  part2 = MIMEText(htmlBody, 'html')

  # Attach parts into message container.  According to RFC 2046, the last part
  # of a multipart message, in this case the HTML message, is best and
  # preferred.
  msg.attach(part1)
  msg.attach(part2)

  return msg


# Send a MIME formatted email
#
def sendMineEmail(mimeEmail):
  # Send the message via local SMTP server.
  s = smtplib.SMTP('localhost')
  # sendmail function takes 3 arguments: sender's address, recipient's address
  # and message to send - here it is sent as one string.
  s.sendmail(mimeEmail['From'], mimeEmail['To'], mimeEmail.as_string())
  s.quit()