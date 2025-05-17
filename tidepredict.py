import logging
import math
from datetime import datetime, timedelta

class TidePredict:
    """Generates a list of the predicted tide at one minute intervals."""
    
    def __init__(self, cons, db):
        self.cons = cons
        self.db = db
        
    def tide_predict(self):
        current_time = datetime.now()
        startproc = False
        restart = False
        tidesecs = 0
        lastime = ''
        #
        # The start time for the tide prediction is the current
        # time minus 24 hours.
        #
        predicted_tide_list = []
        maketime = current_time - timedelta(hours=24)
        then = maketime - timedelta(hours=8)
        then_str = then.strftime(self.cons.TIME_FORMAT)
        #
        # Select the entries from the NOAA predicts table with
        # time tags that are greater than the start time - 8 hours
        #
        trytide = 0
        try:
            predicted_tides = self.db.fetch_predicts(then_str)
            if len(predicted_tides) == 0:
                logging.warning('predicted tide unavailable')
                return None
        except Exception as errmsg:
            logging.warning('Unable to fetch predicted tide '+str(errmsg))
            return None

        for line in predicted_tides:
            this_time = line[0]
            thisto = datetime.strptime(this_time,"%Y-%m-%d %H:%M:%S")
            delta = round(thisto.timestamp()-maketime.timestamp(),2)
            thistide = float(line[1])
            thistate = line[2]
            if lastime == '':
                #
                # for the first entry, initialize last values and continue
                # with the next entry in the list
                #
                lastime = thisto
                lasttide = thistide
                lastdelta = delta
                continue

            if delta >= 0 and lastdelta < 0:
                #
                # When the delta changes sign, it means that the current time
                # is within the current and previous table entries, so perform
                # parameter initialization and processing.
                #   
                simtime = maketime
                tidesecs = 0
                startproc = True
                restart = True
   
            if startproc:
                #
                # Calculate and set the value corresponding to the change
                # in radians per second.
                #
                deltadiff = abs(thisto.timestamp()-lastime.timestamp())
                radians_per_second = self.cons.FULL_TIDE/deltadiff
                if restart:
                    #
                    # On restart, the starting radians are set depending
                    # whether this iteration is from low to high tide
                    # or vice versa.
                    #
                    if lasttide < thistide:
                        radians_start = self.cons.HALF_TIDE*3
                    else:
                        radians_start = self.cons.HALF_TIDE      
                    restart = False
                    tidestart = lastime
                    
                if lasttide < thistide:
                    #
                    # The tide offset is always set to low tide.
                    # The tide difference is used to calculate tide level.
                    #
                    tideoff = lasttide
                else:
                    tideoff = thistide      
                tidediff = abs(thistide - lasttide)
                #
                # Radian seconds is the difference between the time of peak
                # high or low tide and the current time.
                #
                radsecs = round(simtime.timestamp()-tidestart.timestamp(),2)
                radians_start = radians_start+radsecs*radians_per_second
                radians_start = radians_start % (math.pi*2)
                tidelevel = round(
                  math.sin(radians_start)*tidediff/2+(tidediff/2)+tideoff,2)
                #
                # The first entry in the predicted_tide_list is for the
                # current time - 24 hours. The remainder of the list contains
                # predictions for the next 48 hours.
                #
                while simtime < thisto and tidesecs < 172800:
                    predicted_tide_list.append(
                      [simtime,tidesecs,tidelevel,thistate])
                    simtime = simtime+timedelta(seconds=60)
                    radians_start = radians_start+60*radians_per_second
                    radians_start = radians_start % (math.pi*2)   
                    tidelevel = round(
                      math.sin(radians_start)*tidediff/2+
                      (tidediff/2)+tideoff,2)
                    tidesecs += 60
            if tidesecs >= 172800:
                break
            restart = True
            lastime = thisto
            lasttide = thistide
            lastdelta = delta
        return predicted_tide_list
