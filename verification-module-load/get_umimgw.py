
import os
import sys
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
from coords_manager import *

import time


import configparser
config = configparser.ConfigParser()
config.read('settings.ini')


# TODO uniezależnić od miejsca lokalizacji skryptu
GLOBAL_PATH = os.path.join(os.getcwd())
"""
imgw parameters - it is exatly number of column from special file
"""
# IMGW codes
# 29	air temperature
# 77	ground temperature 5 m
# 79	ground temperature 10 m
# 37	relative humidity
code_imgw_air_temp = 29
code_imgw_ground_temp_5 = 77
code_imgw_ground_temp_10 = 79
code_imgw_rel_hum = 37

"""
list of cities for particular visualisation - this is a of list of synoptic imgw stations - polish notation
"""
# malgosia_list = ["KOŁOBRZEG-DŹWIRZYNO",  "ŁEBA", "LĘBORK", "GDAŃSK", "ELBLĄG", "KĘTRZYN",\
#                 "SUWAŁKI", "TORUŃ", "CZĘSTOCHOWA", "KATOWICE", "KRAKÓW", "SANDOMIERZ",\
#                 "BIELSKO-BIAŁA", "ZAMOŚĆ", "ZAKOPANE", "KASPROWY WIERCH"]

"""
list of cities for particular visualisation - this is a of list of synoptic imgw stations - simplified notation
"""
malgosia_list = ["KOLOBRZEG", "KOLOBRZEG-DZWIRZYNO",  "LEBA", "LEBORK", "GDANSK-SWIBNO", "ELBLAG", "KETRZYN",
                 "SUWALKI", "TORUN", "CZESTOCHOWA", "KATOWICE", "KRAKOW", "SANDOMIERZ",
                 "BIELSKO-BIALA", "JELENIA GORA", "KASPROWY WIERCH", "SWINOUJSCIE", "SNIEZKA"]


'''
from stacje_meteorologiczne.csv 
load meteorologic stations. return as dataframe
'''


def load_imgw_coordinates_station():
    """
    load coordinates of stations from stacje_meteorologiczne.csv
    :param filter: filter set of imgw stations
    :param labels: Return labels - names of cities or not.
    :return: DataFrame
    """
    path = GLOBAL_PATH+"/dane_imgw/stacje_meteorologiczne.csv"
    dataframe = pd.read_csv(path, encoding='utf-8',
                            low_memory=False, header=None)

    dataframe[0] = dataframe[0].astype(str)
    dataframe[3] = dataframe[3].astype(float)/10000
    dataframe[2] = dataframe[2].astype(float)/10000
    return dataframe


def filter_namefiles(namefiles, stations):
    if stations == 'all':
        return namefiles
    else:
        returned = []
        for nf in namefiles:
            boolList = [nf.find(s) >= 0 for s in stations]
            if any(boolList):
                returned.append(nf)
        return returned


'''
load weather data from concrete moment time (exactly one hour) as a Pandas DataFrame
convert this DataFrame to Tuple
:param year:
:param month:
:param day:
:param hour:
:param parameter: parameter code accordingly with number of column in csv file
:param latlon_form: True-latlon, False-rowcol form
:return: tuple with 3 arrays,  [lat, lon] and value
'''


def load_imgw_data(year, month, day, hour, parameter, stations):

    path = GLOBAL_PATH+"/dane_imgw/"+str(year)
    namefiles = os.listdir(path)

    namefiles = filter_namefiles(namefiles, stations)
    namefiles.sort()

    direct_paths = [os.path.join(path, namefile) for namefile in namefiles]

    big_frame = pd.DataFrame()
    for f, namefile in zip(direct_paths, namefiles):
        dataframe = pd.read_csv(f, encoding='latin',
                                low_memory=False, header=None)
        dataframe_f = dataframe[(dataframe[2] == year) & (
            dataframe[3] == month) & (dataframe[4] == day) & (dataframe[5] == hour)]
        big_frame = big_frame.append(dataframe_f)

    big_frame[0] = big_frame[0].astype(str)
    cut_big_frame = big_frame[[0, parameter]]

    coordinates_array = load_imgw_coordinates_station()
    result = cut_big_frame.set_index(0).join(
        coordinates_array.set_index(0), lsuffix='_caller', rsuffix='_other')

    lat = np.array(result[2].values.tolist())
    lon = np.array(result[3].values.tolist())

    val = np.array(result[parameter].values.tolist())
    return lat, lon, val


def load_faster_imgw_data(years, parameter, stations):

    big_frame = pd.DataFrame()
    for year in years:
        path = GLOBAL_PATH+"/dane_imgw/"+str(year)
        namefiles = os.listdir(path)
        namefiles = filter_namefiles(namefiles, stations)
        namefiles.sort()
        direct_paths = [os.path.join(path, namefile) for namefile in namefiles]
        for f, in zip(direct_paths):
            dataframe = pd.read_csv(
                f, encoding='latin', low_memory=False, header=None)
            big_frame = big_frame.append(dataframe[[0, 2, 3, 4, 5, parameter]])

    return big_frame


def extract_latlonval(df, coords, year, month, day, hour, param):
    df = df[(df[2] == year) & (df[3] == month)
            & (df[4] == day) & (df[5] == hour)]
    df.loc[:, 0] = df.loc[:, 0].astype(str)
    coords[0] = coords[0].astype(str)
    result = df.set_index(0).join(coords.set_index(
        0), lsuffix='_caller', rsuffix='_other')

    lat = np.array(result["2_other"].values.tolist())
    lon = np.array(result["3_other"].values.tolist())

    val = np.array(result[param].values.tolist())
    return lat, lon, val


def load_altitude_onestation():
    path = os.path.join(GLOBAL_PATH, "dane_imgw", "pl_stacje.csv")
    dataframe = pd.read_csv(path, encoding='utf-8',
                            low_memory=False, header=None)
    dataframe[4] = dataframe[4].astype(float)
    return dataframe[4].values.tolist()


def load_imgw_pl_stations(filter=False):
    path = GLOBAL_PATH+'/dane_imgw/pl_stacje.csv'
    dataframe = pd.read_csv(path, encoding='utf-8',
                            low_memory=False, delimiter=";")
    if filter is True:
        dataframe = dataframe[np.isin(dataframe['stname'], malgosia_list)]

    return dataframe['lon'], dataframe['lat'], dataframe['stname']


'''
load a sequence map of imgw data in rowcol Poland representation
'''


def load_sequence_map(start, param=code_imgw_air_temp, forecast_hour_len=48):
    from numpy import savetxt
    spacetime = np.full(
        (forecast_hour_len, coords_manager.Poland.xlen, coords_manager.Poland.ylen), 0.0)
    for it in range(forecast_hour_len):
        n = start+timedelta(hours=it)
        try:
            spacetime[it] = load_imgw_single(
                n.year, n.month, n.day, n.hour, param=param)
            savetxt(os.path.join(os.getcwd(), '..', 'imgw_proceed_data', 'imgw_csvs', '{}-{}'.format(n.year, n.month),
                                 str(it)), spacetime[it], delimiter=",")
        except BaseException:
            pass

    return spacetime


'''
load a series for concrete localisation in rowcol Poland way
'''


def get_one_series(spacetime, rowcol):
    return spacetime[:, rowcol[0], rowcol[1]].flatten()


'''
make a map of weather parameter in a based of a IMGW synoptic stations
'''


def load_imgw_single(YEAR, MONTH, DAY, HOUR, stations='all', param=code_imgw_air_temp):
    lat_imgw, lon_imgw, nointerpolated_value_imgw = load_imgw_data(
        YEAR, MONTH, DAY, HOUR, param, stations)
    row_imgw, col_imgw = latlon2rowcol(lat_imgw, lon_imgw)
    from scipy.interpolate import Rbf
    rbf = Rbf(row_imgw, col_imgw, nointerpolated_value_imgw, epsilon=0.02)
    tiy = np.linspace(Poland.xmin, Poland.xmax, Poland.xlen)
    tix = np.linspace(Poland.ymin, Poland.ymax, Poland.ylen)
    # w meshgrid wyrażam w reprezentacji rowcol Globalnej
    YI, XI = np.meshgrid(tix, tiy)
    interpolated_value_imgw = rbf(XI, YI)
    return np.array(interpolated_value_imgw)

    # node - reprezentacja rowcol Globalnej


def load_imgw_single_point(YEAR, MONTH, DAY, HOUR, node, stations='all', param=code_imgw_air_temp):
    lat_imgw, lon_imgw, nointerpolated_value_imgw = load_imgw_data(
        YEAR, MONTH, DAY, HOUR, param, stations)
    row_imgw, col_imgw = latlon2rowcol(lat_imgw, lon_imgw)
    from scipy.interpolate import Rbf
    rbf = Rbf(row_imgw, col_imgw, nointerpolated_value_imgw, epsilon=0.02)
    # w meshgrid wyrażam w reprezentacji rowcol Globalnej
    interpolated_value_imgw = rbf(node[1], node[0])
    return round(float(interpolated_value_imgw), 2)


def mongo_load_faster_sequence_single_point(d, node, stations='all', param=code_imgw_air_temp, len=30):
    from scipy.interpolate import Rbf
    import pymongo
    import traceback

    start = d
    coords = load_imgw_coordinates_station()
    first = d.year
    last = (start+timedelta(hours=len)).year
    years = list(range(first, last+1))
    df = load_faster_imgw_data(years, param, stations)
    print("database launching")
    database = pymongo.MongoClient(config["DEFAULT"]["database"])
    mydb = database[config['DEFAULT']['collectionname']]
    mycol = mydb["IMGW"]

    for d in [start+timedelta(hours=it) for it in range(len)]:
        print("d {}".format(d))
        lat_imgw, lon_imgw, nointerpolated_value_imgw = extract_latlonval(
            df, coords, d.year, d.month, d.day, d.hour, param)
        row_imgw, col_imgw = latlon2rowcol(lat_imgw, lon_imgw)
        try:
            rbf = Rbf(row_imgw, col_imgw,
                      nointerpolated_value_imgw, epsilon=0.02)
            # TODO upewnić się czy kolejność jest dobra tutaj
            value = np.round(rbf(node[1], node[0]), 3)
            print(d)

            mycol.insert_one({"date": d, "stations": stations,
                              "row": node[0], "col": node[1], "value": value})
        except Exception:
            print("error - matrix is singular for ", d)
            traceback.print_exc()


def mongo_load_um_series(start, node, number_forecasts):

    # a - anticipation
    import json
    import pymongo

    def k2c(t):
        return t-273.15

    def c2k(t):
        return t+273.15

    start_timer = time.process_time()

    print("config!!!!!", config['DEFAULT']['database'])
    database = pymongo.MongoClient(config['DEFAULT']['database'])
    mydb = database[config['DEFAULT']['collectionname']]
    mycoll = mydb["UM"]

    um_series = []
    for i in range(number_forecasts):

        d = start + timedelta(days=i)
        YEAR, MONTH, DAY, HOUR = d.year, d.month, d.day, d.hour
        # TODO uniezależnić to miejsce od miejsca uruchamiania skryptu
        path = "um_data/{}_{}/{}-{}-{}T{}.txt".format(
            node[0], node[1], YEAR, MONTH, DAY, HOUR)

        #print("iteration number is {} path is: {} ".format(i, path))
        f = open(path, 'r')
        forecast = json.loads(f.read())
        print(path)

        try:
            values = [round(k2c(i), 3) for i in forecast['data'][::4]]
            for i, value in enumerate(values):

                dbrow = {"start_forecast": d, "date": d +
                         timedelta(hours=i), "row": node[0], "col": node[1], "value": value}
                mycoll.insert_one(dbrow)
                print("start_forecast", d, "date", d +
                      timedelta(hours=i), "value=", value)
        except TypeError as e:
            print("for {d} we don't have forecast".format(d=d))

    end_timer = time.process_time()

    print("performance time is {}".format(end_timer-start_timer))
