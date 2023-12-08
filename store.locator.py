#!/usr/bin/env python3

import glob
import pprint
import os
import requests
import sys
import urllib.parse

"""
./store.locator.py --storeslist==INPUT-FILE

Performs a fetch of Google Map data for store locations based on the contents of a .csv
file of format 'Site ID, Site Name,Street Address,City,State'.

Store location and associated Google Map is written to html/index.html in the pwd

eric.stanfield@wwt.com

"""

GMAPAPIKEY = "INSERT GOOGLE MAPS API KEY HERE"


def main():
    args = sys.argv
    #args = ("store.locator.py", "--storeslist=2024.stores.csv")

    if (len(args) != 2) or ("--storeslist=" not in args[1]):
        print("Syntax: store.locator.py --storeslist=INPUT-FILE")
        sys.exit()

    inputFile = args[1][13::]

    try:
        f = open(inputFile, "r")
    except IOError:
        print(f'Failed to open input file "{inputFile}"')
        sys.exit()

    # prep the input data
    stores = parseInputFile(f)

    # fetch full Google Map address and lat/lng for each store
    storesCoords = fwdGeoLocate(stores)
  
    # group stores by state and build per-state HTML package
    state = []
    locations = []

    if len(storesCoords) > 1:
        for store in storesCoords:
            if not state:  # initial target state code
                state = store[2][-2::]
                locations = [store]
            elif len(locations) == 9: # google Distance API only supports a 10x10 matrix, so send a smaller batch for this state
                routeMatrixJSON = requestRouteMatrix(locations)
                buildHTMLPayload(locations, routeMatrixJSON)
                locations = [store]                
            elif store[2][-2::] == state:  # another instance of target state code
                locations.append(store)
            elif store[2][-2::] != state:   # a new state code  
                routeMatrixJSON = requestRouteMatrix(locations)
                buildHTMLPayload(locations, routeMatrixJSON)  # build HTML for this state's locs
                state = store[2][-2::]  # set new target state code
                locations = [store]
        # flush through the last batch
        routeMatrixJSON = requestRouteMatrix(locations)
        buildHTMLPayload(locations, routeMatrixJSON)
    else:
        # print("WARNING!!! SINGLE STORE")
        routeMatrixJSON = requestRouteMatrix(storesCoords)
        buildHTMLPayload(storesCoords, routeMatrixJSON)  # if there is only one store in the list

    buildHTMLIndex("Store Locator")


def parseInputFile(f):
    """Strips the header row from a CSV file and builds a list out of the addresses it contains

    Args:
        f (file): CSV file containing store data of format
                  Site ID,Site Name,Street Address,City,State
                  MLO-251,MLO Los Angeles Distribution Center,15541 East Gale,City of Industry,CA

    Returns:
        stores (list): A list of store addresses reformatted as follows
                       stores[0] = Site ID
                       stores[1] = Site Name
                       stores[2] = Address, City, State
    """
    storesCSV = f.readlines()
    stores = []

    for store in storesCSV[1::]:  ####### CHANGE THIS TO CONSUME ALL ROWS AFTER HEADER [1::]
        x = store.split(",")
        stores.append([x[0], x[1], (x[2] + ", " + x[3] + ", " + (x[4][0::]).strip())])

    return stores



def fwdGeoLocate(stores):
    """Calls Google Map's geocode API to pull lat/lng and full street address for each store

    Args:
        stores (list): A list of store locations arranged as follows
                       stores[0] = Site ID
                       stores[1] = Site Name
                       stores[2] = Address, City, State

    Returns:
        storeCoords (list): A list of store locations sorted by state and arranged as follows
                       stores[0] = Site ID
                       stores[1] = Site Name
                       stores[2] = Address, City, State
                       stores[3] = Google Maps full street address
                       stores[4] = lattitude
                       stores[5] = longitude
    """
    geocodeAPI = "https://maps.googleapis.com/maps/api/geocode/json?address="
    storesCoords = []

    for store in stores:
        address = urllib.parse.quote(store[2])

        response = requests.get(geocodeAPI + address + "&key=" + GMAPAPIKEY)
        jsonResponse = response.json()

        formattedAddress = jsonResponse["results"][0]["formatted_address"]       
        geometry = jsonResponse["results"][0]["geometry"]
        location = geometry["location"]
        lat = location["lat"]
        lng = location["lng"]

        storesCoords.append([store[0], store[1], store[2], formattedAddress, lat, lng])

    # print(f"GEOLOCATING ADDRESS: {store[2]}...\n")

    return sorted(storesCoords, key=lambda store: store[2][-2::])


def requestRouteMatrix(locations):
    """Calls Google Map's distance matrix API to fetch distance and travel times between all locations, full mesh

    Args:
        locations (list): A list of store locations sorted by state and arranged as follows
                          stores[0] = Site ID
                          stores[1] = Site Name
                          stores[2] = Address, City, State
                          stores[3] = Google Maps full street address
                          stores[4] = lattitude
                          stores[5] = longitude

    Returns:
        routeMatrixJSON (dict): JSON data from the API dumped in to a dictionary object
    """
    addresses = ""
    distanceMatrixAPI = "https://maps.googleapis.com/maps/api/distancematrix/json"

    for location in locations:
        addresses = addresses + urllib.parse.quote(location[3]) + "%7C"

    queryURL = (
        distanceMatrixAPI
        + "?destinations="
        + addresses[0:-3]
        + "&origins="
        + addresses[0:-3]
        + "&key="
        + GMAPAPIKEY
        + "&units=imperial"
    )
    # print(f"SENDING REQUEST: {queryURL}")
    response = requests.get(queryURL)
    routeMatrixJSON = response.json()
    # pprint.pprint(routeMatrixJSON)
    return routeMatrixJSON


def createStaticMap(locations):
    """Create HTML to embed Google Map w/store location markers

    Args:
        locations (list): A list of store locations arranged as follows
                          locations[0] = Site ID
                          locations[1] = Site Name
                          locations[2] = Address, City, State
                          locations[3] = Google Maps full street address
                          locations[4] = lattitude
                          locations[5] = longitude

    Returns:
        (string): The resulting HTML map embed code
    """
    staticMapAPI = "https://maps.googleapis.com/maps/api/staticmap?size=800x800&zoom=6"
    markers = ""

    for location in locations:
        markers = markers + "&markers=color:red%7C" + "label:" + location[0] + "%7C" + str(location[4]) + "," + str(location[5])
                   
    mapLink = (staticMapAPI + markers + "&key=" + GMAPAPIKEY)              

    return "<img src='" + mapLink + "'>"


def createDistanceTable(locations, routeMatrixJSON):
    """Create HTML for a table that contains distance and travel times between all locations, full mesh

    Args:
        locations (list): A list of store locations arranged as follows
                          locations[0] = Site ID
                          locations[1] = Site Name
                          locations[2] = Address, City, State
                          locations[3] = Google Maps full street address
                          locations[4] = lattitude
                          locations[5] = longitude
        jsonResponse (dict): A dictionary object containing JSON data from the distance matrix API

    Returns:
        (string): The resulting HTML table code
    """
            
    optimizedWaypointsMapLink = ""
    
    destinations = routeMatrixJSON["destination_addresses"]
    
    # Waypoints URL build
    if(destinations):
        optimizedWaypointsMapLink = '<button>\n<a href=https://www.google.com/maps/dir/?api=1&origin=' + urllib.parse.quote(destinations[0])
        
        if len(destinations) > 1:
            optimizedWaypointsMapLink = optimizedWaypointsMapLink + '&destination=' + urllib.parse.quote(destinations[-1])
        
        if len(destinations) > 2:
            optimizedWaypointsMapLink = optimizedWaypointsMapLink + '&waypoints='
            for destination in destinations[1:-2]:
                optimizedWaypointsMapLink = optimizedWaypointsMapLink + urllib.parse.quote(destination) + "%7C"

        optimizedWaypointsMapLink = optimizedWaypointsMapLink + ' target="_new">Click Here For Optimized Route Between Stores Map</a>\n</button>\n<p></p>\n'

    # TABLE HEADER
    tableHeaderRowHTML = "<tr><th class='knockout'></th>"

    for location in locations:
        tableHeaderRowHTML = (
            tableHeaderRowHTML + "<td class='columnHeader'><div class='storeID'>Store# "
                + location[0]
                + "</div><div class='storeAddr'>"
                + location[3]
                + "</div></td>"
        )
    tableHeaderRowHTML = tableHeaderRowHTML + "</tr>\n"

    # TABLE DATA ROWS
    tableDataRowHTML = ""

    x = 0

    tableDataRowHTML = tableDataRowHTML + "<tr>"
    for destination in destinations:
        tableDataRowHTML = tableDataRowHTML + (
            "<td class='rowHeader'><div class='storeID'>Store# "
            + locations[x][0]
            + "</div><div class='storeAddr'>"
            + locations[x][3]
            + "</div></td>"
        )

        try:
            destinationIndex = destinations.index(locations[x][3]) #Need a regexp or something to get a looser match since Google Map address returns are problematic
        except:
            print(f"Lookup Failure in Destinations array: {destinations}")
            
        rows = routeMatrixJSON["rows"]
        row = rows[destinationIndex]["elements"]
        for element in row:
            tableDataRowHTML = (
                tableDataRowHTML + "<td class='data'>Miles: " + element["distance"]["text"] + "<br>"
            )
            tableDataRowHTML = (
                tableDataRowHTML + "Hours: " + element["duration"]["text"] + "</td>"
            )
        tableDataRowHTML = tableDataRowHTML + "</tr>\n"
        x = x + 1

    return optimizedWaypointsMapLink + "<table>" + tableHeaderRowHTML + tableDataRowHTML + "</table>"


def buildHTMLPayload(locations, routeMatrixJSON):
    # htmlDocTitle = "<title>" + locations[0][2][-2::] + "</title>"
    # htmlHeader = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n' + 
    #               '<link rel="stylesheet" href="css/styles.css">\n' +
    #               '<script src="js/store.locator.js"></script>\n' + 
    #               htmlDocTitle + '\n</head>\n<body>\n')
    # htmlFooter = "\n</body>\n</html>"

    # have to pull in the stylesheet again so it applies to the iframe
    htmlIFrameStyles = '<link rel="stylesheet" href="css/styles.css">'
    
    # build the embedded map with markers
    htmlMap = createStaticMap(locations)

    # build the distance/time matrix table
    htmlTable = createDistanceTable(locations, routeMatrixJSON)

    outputFilename = locations[0][2][-2::] + "-0.html"

    if os.path.isfile("html/" + outputFilename):
        existingFiles = glob.glob("html/" + locations[0][2][-2::] + "*.html")
        outputFilename = locations[0][2][-2::] + "-" + str(len(existingFiles)) + ".html"

    outputFile = open("html/" + outputFilename, "w")

    outputFile.writelines(htmlIFrameStyles + htmlMap + "<p>" + htmlTable)

    outputFile.close()

    return None

def buildHTMLIndex(pageTitle):
    htmlDocTitle = "<title>" + pageTitle + "</title>"
    htmlHeader = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n' + 
                  '<link rel="stylesheet" href="css/styles.css">\n' +
                  '<script src="js/store.locator.js"></script>\n' +
                  htmlDocTitle + '\n</head>\n<body>\n')
    htmlContent = '<div id="contentArea">\n<iframe id="googleMapBox">\n</iframe>\n</div>\n'
    htmlFooter = "\n</body>\n</html>"

    # build a menu area with basic dropdown to access per-state pages
    htmlMenuBox = '<div id="menuBox">\n'
    htmlMenuBox = htmlMenuBox + ('<select name="stateSelector" id="stateSelector">\n')
    
    dirList = os.listdir("html/")
    
    mapFiles = sorted(dirList)
    
    for filename in mapFiles:
        if filename[-5::] == ".html" and filename != "index.html":
            if filename[-7:-5] == "-0":
                htmlMenuBox = htmlMenuBox + '<option value="' + filename + '">' + filename[0:-7] + '</option>\n'
            else:
                htmlMenuBox = htmlMenuBox + '<option value="' + filename + '">' + filename[0:-5] + '</option>\n'

    htmlMenuBox = htmlMenuBox + '</select>\n'

    htmlMenuBox = htmlMenuBox + '<button id="stateSelectorButton">Submit</button>\n</div>\n'

    outputFile = open("html/index.html", "w")

    outputFile.writelines(htmlHeader + htmlMenuBox + htmlContent + htmlFooter)

    outputFile.close()

    return None


if __name__ == "__main__":
    main()
