# Domoticz Spotify
Python plugin for Domoticz: Control spotify using domoticz 
See http://www.domoticz.com for more information on the platform.  
Discussion thread about this plugin: https://www.domoticz.com/forum/viewtopic.php?f=xxxx.

## Requirements:
* Spotify premium account
* Domoticz with python plugin framework enabled
* Python3.5 or higher

## Installation:
* > cd ~/domoticz/plugins
* > git clone https://github.com/DaanJJansen/domoticz-spotify spotify (or any other target directory you like)
* You should now have a ~/domoticz/plugins/spotify directory that contains the plugin.py. In the future you can update the plugin by going into this directory and do a 'git pull'.
* Restart Domoticz
* Add the plugin in the Domoticz hardware configuration screen
* Create a client ID at spotify (https://developer.spotify.com/dashboard/applications)
	* Enter all fields as desired
	* Enter just created client id and client secret into hardware parameters
	* Go to 'edit setting' and 'http://localhost' as redirect URI
	* In your webbrowser, navigate to this url: https://accounts.spotify.com/authorize?client_id=[YOURCLIENT_ID]&redirect_uri=http://localhost&response_type=code&scope=user-read-playback-state+user-modify-playback-state
	* If all go's well, you are being redirect to localhost returning a 404, with a code in the query parameters, copy this code into the hardware parameters
	* Refresh interval spotify devices: devices using spotify connect go offline and offline, at refresh devices are being updated on de domoticz switch selector
* Add
* Add newly created Spotify-device from your device tab

## Usage:
* Update user variable [name]-searchTxt with the query parameter by using the type of search and the search string. The following types could be used:
	* artist -> find artist, eg searchTxt: 'artist coldplay' This will play the top tracks of Coldplay
	* track --> find song, eg searchTxt: 'track song 2'. Will play 10 tracks which matches with your search string
	* album --> find album, eg searchTxt: 'album Ten'. Will play album 10 by Pearl Jam
	* playlist --> find playlist, eg searchTxt: 'playlist discover weekly'. Will play the complete playlist for you.
* On the spotify-device select device on which playback needs to be started

## History:
**version 0.1**
- Initial setup