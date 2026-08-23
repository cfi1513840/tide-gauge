"""tideprocess.py

Post-processes a list of (time, tide_ft) measurements to identify
high/low tide epochs -- used to annotate the local Tk display and
tide.html with "High Tide" / "Low Tide" markers at the actual turning
points, not just wherever the raw curve happens to peak.

ProcTide detects a turning point via a 15-sample rolling average of
the tide values: once the average has moved more than 0.05 ft from
its value at the last 15-sample checkpoint, it records the min (for a
low->high transition) or max (high->low) tide seen since the previous
turning point as the epoch, then starts tracking the new trend.
"""
class ProcTide:
    """Analyzes a rolling window of tide measurements to detect high
    and low tide turning points -- see module docstring for the
    approach. __init__ processes the initial (typically 24-hour)
    tide_list; update_tide_list() re-runs the same detection when new
    measurements are appended.
    """
    def __init__(self, tide_list):
        self._find_epochs(tide_list)
        
    def update_tide_list(self, tide_list):
        self._find_epochs(tide_list)
        return self.tide_list
        
    def _find_epochs(self, tide_list):
        self.tide_list = tide_list
        self.trend = ''
        epochs = []
        self.tide_average = [0 for x in range(0,15)]
        self.last_average = 0
        self.max_tide = float('-inf')
        self.min_tide = float('inf')
        new_tide_list = []
        for index, entry in enumerate(self.tide_list):
            new_tide_list.append([entry[0], entry[1], self.trend])
            self.index = index
            if entry[1] > self.max_tide:
                self.max_tide = entry[1]
                self.max_tide_time = entry[0]
            if entry[1] < self.min_tide:
                self.min_tide = entry[1]
                self.min_tide_time = entry[0]
            self.tide_average = self.tide_average[1:]+[entry[1]]
            if index != 0 and index % 15 == 0:
                self.average = sum(self.tide_average)/len(self.tide_average)
                if self.last_average == 0:
                    self.last_average = self.average
                    continue
                if self.average > self.last_average + 0.05:
                    if self.trend == 'low':
                        epochs.append([self.min_tide_time,self.trend])
                        self.min_tide = float('inf')
                        self.max_tide = float('-inf')                        
                    self.trend = 'high'
                elif self.average < self.last_average - 0.05:
                    if self.trend == 'high':
                        epochs.append([self.max_tide_time,self.trend])
                        self.min_tide = float('inf')
                        self.max_tide = float('-inf')                            
                    self.trend = 'low'
                self.last_average = self.average
        for index, entry in enumerate(self.tide_list):
            for epoch_entry in epochs:
                if entry[0] == epoch_entry[0]:
                    self.tide_list[index][2] = epoch_entry[1]

    def get_tide_list(self):
        return self.tide_list
