#
#   Spotify Plugin
#
#   Daan Jansen, 2018
#   https://github.com/DaanJJansen/domoticz-spotify
#

"""
<plugin key="Spotify" name="Spotify Plugin" author="djj" version="0.1" wikilink="https://github.com/DaanJJansen/domoticz-spotify" externallink="https://api.spotify.com">
    <params>
        <param field="Address" label="Domoticz IP Address" width="200px" required="true" default="localhost"/>
        <param field="Port" label="Port" width="40px" required="true" default="8080"/>
        <param field="Mode2" label="Client ID" width="200px" required="true" default=""/>
        <param field="Mode3" label="Client Secret" width="200px" required="true" default=""/>
        <param field="Mode4" label="Code" width="200px" required="true" default=""/>
        <param field="Mode5" label="Refresh interval spotify devices" width="100px" required="true">
            <options>
                <option label="N/A - Only at start up" value=0/>
                <option label="30 seconds" value=1/>
                <option label="5 minutes" value=10 default="true"/>
                <option label="15 minutes" value=30/>
                <option label="30 minutes" value=60/>
                <option label="60 minutes" value=120/>
            </options>
        </param>
    	<param field="Mode6" label="Debug" width="75px">
    		<options>
        		<option label="True" value="Debug"/>
        		<option label="False" value="Normal"  default="True" />
    		</options>
    	</param>
    </params>
</plugin>
"""

try:
    import Domoticz
except ImportError:
    import fakeDomoticz as Domoticz


import urllib.request
import urllib.error
import urllib.parse
import base64
import json
import time

#DEFINES
SPOTIFYDEVICES = 1


#############################################################################
#                      Domoticz call back functions                         #
#############################################################################
class BasePlugin:
    def __init__(self):
        self.spotifyToken = {"access_token":"",
                             "refresh_token":"",
                             "retrievaldate":"",
                             "searchTxt":""
                             }
        self.tokenexpired = 3600
        self.spotifyAccountUrl = "https://accounts.spotify.com/api/token"
        self.spotifyApiUrl = "https://api.spotify.com/v1"
        self.heartbeatCounter = 1
        self.blError = False
        self.blDebug = False
        

    def onStart(self):

        

        if Parameters["Mode6"] == "Debug":
            self.blDebug = True

        if not self.getUserVar():
            self.blError = True
            return None
            

        for key, value in self.spotifyToken.items():
            if key != 'searchTxt' and value == '':
                Domoticz.Log("Not all spotify token variables are available, let's get it")
                if not self.spotAuthoriseCode(Parameters["Mode4"]):
                    self.blError = True
                    return None
                break

        self.checkDevices()

        Domoticz.Heartbeat(30)


    def checkDevices(self):
        Domoticz.Log("Checking if devices exis")
        
        if SPOTIFYDEVICES not in Devices:
            Domoticz.Log("Spotify devices selector does not exist, creating device")

            strSelectorNames = 'Off'
            dictOptions = self.buildDeviceSelector(strSelectorNames)
            
            Domoticz.Device(Name="devices", Unit=SPOTIFYDEVICES, TypeName="Selector Switch", Switchtype=18, Options = dictOptions).Create()
        else:
            self.updateDeviceSelector()

    def updateDeviceSelector(self):
        if self.blDebug:
            Domoticz.Log("Updating spotify devices selector")
        strSelectorNames = Devices[SPOTIFYDEVICES].Options['LevelNames']
        dictOptions = self.buildDeviceSelector(strSelectorNames)

        Devices[SPOTIFYDEVICES].Update(nValue=Devices[SPOTIFYDEVICES].nValue, sValue=Devices[SPOTIFYDEVICES].sValue, Options=dictOptions)
        
            
    def buildDeviceSelector(self, strSelectorNames):

        spotDevices = self.spotDevices()
        if self.blDebug:
            Domoticz.Log('JSON Returned from spotify listed available devices: ' + str(spotDevices))
            
        strSelectorActions = ''
        self.spotArrDevices = {}

        lstSelectorNames=strSelectorNames.split("|")
        
        x=1
        while x<len(lstSelectorNames):
            strSelectorActions += '|'
            x+=1

        
        intCounter = (len(lstSelectorNames) * 10)

        for device in spotDevices['devices']:
            if device['name'] not in lstSelectorNames:
                strSelectorNames += '|' + device['name']
                strSelectorActions += '|'
                self.spotArrDevices.update({str(intCounter):device['id']})
                intCounter += 10
            else:
                self.spotArrDevices.update({str(lstSelectorNames.index(device['name'])*10):device['id']})

        if self.blDebug:
            Domoticz.Log('Local array listing selector level with deviceids: ' + str(self.spotArrDevices))
                

        dictOptions = {"LevelActions": strSelectorActions,
                       "LevelNames": strSelectorNames,
                       "LevelOffHidden": "true",
                       "SelectorStyle": "1"}

        return dictOptions
    
            

        

    def spotGetBearerHeader(self):
        tokenSecElapsed = time.time() - float(self.spotifyToken['retrievaldate'])
        if tokenSecElapsed > self.tokenexpired:
            Domoticz.Log('Token expired, getting new one using refresh_token')
            self.spotGetRefreshToken()

        return {"Authorization": "Bearer " + self.spotifyToken['access_token']}

        
        

    def spotDevices(self):
        try:
            url = self.spotifyApiUrl + '/me/player/devices'
            headers = self.spotGetBearerHeader()

            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req)

            strResponse = response.read().decode('utf-8')
            return json.loads(strResponse)
        
        except urllib.error.URLError as err:
            Domoticz.Error("Unkown error: code: %s, msg: %s" % (str(err.code), str(err.args)))
            return None
            
            
        

    def getUserVar(self):
        variables = DomoticzAPI({'type':'command','param':'getuservariables'})
        try:
            if variables:
                valuestring = ""
                missingVar = []
                if "result" in variables:
                    for intVar in self.spotifyToken:
                        intVarName = Parameters["Name"] + '-' + intVar
                        try:
                            result = next((item for item in variables["result"] if item["Name"] == intVarName))
                            self.spotifyToken[intVar] = result['Value']
                        except:
                            missingVar.append(intVar)


                    if len(missingVar) > 0:
                        strMissingVar = ','.join(missingVar)
                        Domoticz.Log("User Variable {} does not exist. Creation requested".format(strMissingVar))
                        for variable in missingVar:
                            DomoticzAPI({"type":"command","param":"saveuservariable","vname":Parameters["Name"] + '-' + variable,"vtype":"2","vvalue":""})
                else:
                    raise Exception("Cannot read the uservariable holding the persistent variables")
                
                return True
            else:
                raise Exception("Cannot read the uservariable holding the persistent variables")
            
        except Exception as error:
            Domoticz.Error(str(error))

        
            

    def saveUserVar(self):

        for intVar in self.spotifyToken:
            intVarName = Parameters["Name"] + '-' + intVar
            DomoticzAPI({"type":"command","param":"updateuservariable","vname":intVarName,"vtype":"2","vvalue":str(self.spotifyToken[intVar])})

    def spotGetRefreshToken(self):
        try:

            url = self.spotifyAccountUrl
            headers = self.returnSpotifyBasicHeader()

            data = {'grant_type':'refresh_token',
                    'refresh_token': self.spotifyToken['refresh_token']}
            data = urllib.parse.urlencode(data)

            req = urllib.request.Request(url, data.encode('ascii'), headers)
            response = urllib.request.urlopen(req)

            strResponse= response.read().decode('utf-8')
            if self.blDebug:
                Domoticz.Log('Spotify response accestoken based on refresh: ' + str(strResponse))
                
            jsonResponse = json.loads(strResponse)

            self.saveSpotifyToken(jsonResponse)
        except:
            Domoticz.Error('Seems something with wrong with token response from spotify') 

    def returnSpotifyBasicHeader(self):

        client_id = Parameters["Mode2"] 
        client_secret = Parameters["Mode3"] 
        login = client_id + ':' + client_secret
        base64string = base64.b64encode(login.encode())
        header = {'Authorization': 'Basic ' + base64string.decode('ascii')}

        return header
        
    
   

    def spotAuthoriseCode(self, code):
        try:
            if Parameters["Mode2"] == "" or Parameters["Mode3"] == "":
                raise Exception('No client_id and/or client_secret is set in hardware parameters')

            url = self.spotifyAccountUrl
            data = {'grant_type':'authorization_code',
                    'code':code,
                    'redirect_uri':'http://localhost'}
            data = urllib.parse.urlencode(data)
            headers = headers = self.returnSpotifyBasicHeader()

            try:
                req = urllib.request.Request(url, data.encode('ascii'), headers)
                response = urllib.request.urlopen(req)

                strResponse= response.read().decode('utf-8')
                if self.blDebug:
                    Domoticz.Log('Spotify tokens based on authorisation code: ' + str(strResponse))
                jsonResponse = json.loads(strResponse)
                    

                self.saveSpotifyToken(jsonResponse)

                return True
                   
            except:
               Domoticz.Error('Bad request to spotify, code entered in hardware parameters could one be used once. Please get a new one')
            
        except Exception as error:
            Domoticz.Error(error)

            
            
    def saveSpotifyToken(self, response):
        try:
            for intVar in self.spotifyToken:
                if intVar in response:
                    self.spotifyToken[intVar] = response[intVar]
            self.spotifyToken['retrievaldate'] = time.time()
            Domoticz.Log('Succesfully got spotify tokens, saving data in user domoticz user variables')
            self.saveUserVar()
        except:
            Domoticz.Error('Seems something with wrong with token response from spotify')

    def spotSearch(self, input, type):

        
        url = self.spotifyApiUrl + "/search?q=%s&type=%s&market=NL&limit=10" % (urllib.parse.quote(input), type)
        if self.blDebug:
            Domoticz.Log('Spotify search url: ' + str(url))
            
        headers = self.spotGetBearerHeader()

        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req)

        jsonResponse = json.loads(response.read().decode('utf-8'))
        foundItems = jsonResponse['%ss' % type]['items']

        if self.blDebug:
            Domoticz.Log('First result of spotify search: ' + str(foundItems[0]))
            
        rsltString = 'Found ' + type + ' ' + foundItems[0]['name']
        if type == 'track':
            tracks = []
            for track in foundItems:
                tracks.append(track['uri'])
            returnData = {"uris": tracks}
        else:
            returnData = {"context_uri": foundItems[0]['uri']}

        if type  == 'album' or type == 'track':
            rsltString += ' by ' + foundItems[0]['artists'][0]['name']
            
        Domoticz.Log(rsltString) 
        return returnData
    
    def spotPlay(self, input, deviceLvl):

        try:

            if deviceLvl not in self.spotArrDevices:
                raise urllib.error.HTTPError(url='',msg='',hdrs='', fp='', code=404)
            
            device = self.spotArrDevices[deviceLvl]
            url = self.spotifyApiUrl + "/me/player/play?device_id=" + device  
            headers = self.spotGetBearerHeader()

            data = json.dumps(input).encode('utf8')


            req = urllib.request.Request(url, headers=headers, data=data, method='PUT')
            response = urllib.request.urlopen(req)
            Domoticz.Log("Succesfully started playback")

        except urllib.error.HTTPError as err:
            if err.code == 403:
                Domoticz.Error("Error playback, you need to be premium member")
            elif err.code == 400:
                Domoticz.Error("Error playback, right scope requested?")
            elif err.code == 404:
                Domoticz.Error("Device not found, went offline?")
            else:
                Domoticz.Error("Unkown error, msg: " + str(err.msg))
        

    def onHeartbeat(self):
        if not self.blError:
            if Parameters["Mode5"] != "0" and self.heartbeatCounter == int(Parameters["Mode5"]):
                if self.blDebug:
                    Domoticz.Log('Heartbeat')
                self.updateDeviceSelector()
                self.heartbeatCounter = 1
            else:
                self.heartbeatCounter += 1    
            return True

            

    def onCommand(self, Unit, Command, Level, Hue):

        variables = DomoticzAPI({'type':'command','param':'getuservariables'})
        searchVariable = next((item for item in variables["result"] if item["Name"] == Parameters["Name"] + '-searchTxt'))
        searchString = searchVariable['Value']
        Domoticz.Log('Looking for ' + searchString)
        searchResult = None

        if searchString != "":
            for type in ['artist','track','playlist','album']:
                if type in searchString:
                    strippedSearch = searchString.replace(type,'').lstrip()
                    if self.blDebug:
                        Domoticz.Log('Search type: ' + type)
                        Domoticz.Log('Search string: ' + strippedSearch)
                    searchResult = self.spotSearch(strippedSearch,type)
                    break

        if not searchResult:
            Domoticz.Error("No correct type found in search string, use either artist, track, playlist or album")
        else:
            self.spotPlay(searchResult,str(Level))

_plugin = BasePlugin()

def onStart():
    _plugin.onStart()

def onHeartbeat():
    _plugin.onHeartbeat()

def onCommand(Unit, Command, Level, Hue):
    _plugin.onCommand(Unit, Command, Level, Hue)


#############################################################################
#                         Domoticz helper functions                         #
#############################################################################


def DomoticzAPI(APICall):
    resultJson = None
    url = "http://{}:{}/json.htm?{}".format(Parameters["Address"], Parameters["Port"], urllib.parse.urlencode(APICall, safe="&="))
    #Domoticz.Debug("Calling domoticz API: {}".format(url))
    try:
        req = urllib.request.Request(url)
        if Parameters["Username"] != "":
            Domoticz.Debug("Add authentification for user {}".format(Parameters["Username"]))
            credentials = ('%s:%s' % (Parameters["Username"], Parameters["Password"]))
            encoded_credentials = base64.b64encode(credentials.encode('ascii'))
            req.add_header('Authorization', 'Basic %s' % encoded_credentials.decode("ascii"))

        response = urllib.request.urlopen(req)

        if response.status == 200:
            resultJson = json.loads(response.read().decode('utf-8'))
            if resultJson["status"] != "OK":
                Domoticz.Error("Domoticz API returned an error: status = {}".format(resultJson["status"]))
                resultJson = None
        else:
            Domoticz.Error("Domoticz API: http error = {}".format(response.status))
    except:
        Domoticz.Error("Error calling '{}'".format(url))
        return None
    return resultJson




#############################################################################
#                       Device specific functions                           #
#############################################################################

