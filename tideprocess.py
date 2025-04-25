class ProcTide:
    """Process incoming tide data and set high and low tide tags"""
    def __init__(self, tide_list):
        self.tide_list = tide_list
        self.trend = ''
        epochs = []
        self.tide_average = [0 for x in range(0,15)]
        self.last_average = 0
        self.max_tide = -99
        self.min_tide = 99
        for index, entry in enumerate(self.tide_list):
            self.tide_list[index][2] = self.trend
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
                        self.min_tide = 99
                        self.max_tide = -99                        
                    self.trend = 'high'
                elif self.average < self.last_average - 0.05:
                    if self.trend == 'high':
                        epochs.append([self.max_tide_time,self.trend])
                        self.min_tide = 99
                        self.max_tide = -99                            
                    self.trend = 'low'
                self.last_average = self.average
        for index, entry in enumerate(self.tide_list):
            for epoch_entry in epochs:
                if entry[0] == epoch_entry[0]:
                    self.tide_list[index][2] = epoch_entry[1]

    def get_tide_list(self):
        return self.tide_list
        
    def update_tide_list(self, tide_list, tide):
        """
         Insert new tide measurement into the tide list and
         check for the occurrence of high or low tide.
         """
        from datetime import datetime, timedelta
        current_time = datetime.now()
        for index, entry in enumerate(tide_list):
            if datetime.strptime(
              entry[0],"%Y-%m-%d %H:%M:%S") >= current_time - timedelta(hours=24):
                break
        for findex in range(0,index):
            tide_list.pop(0)
        tide_time = datetime.strftime(current_time, "%Y-%m-%d %H:%M:%S")            
        tide_list.append([tide_time, tide, ''])
        self.index += 1
        if tide > self.max_tide:
            self.max_tide = tide
            self.max_tide_time = tide_time
        if tide < self.min_tide:
            self.min_tide = tide
            self.min_tide_time = tide_time
        self.tide_average = self.tide_average[1:]+[tide]
        update_time = None
        if self.index % 15 == 0:
            self.average = sum(self.tide_average)/len(self.tide_average)
            if self.average > self.last_average + 0.05:
                if self.trend == 'low':
                    update_time = self.min_tide_time
                    update_trend = self.trend
                    self.min_tide = 99
                    self.max_tide = -99                        
                self.trend = 'high'
            elif self.average < self.last_average - 0.05:
                if self.trend == 'high':
                    update_time = self.max_tide_time
                    update_trend = self.trend
                    self.min_tide = 99
                    self.max_tide = -99                            
                self.trend = 'low'
            self.last_average = self.average
        if update_time:
            #
            # Update tide list with high or low tide event
            #
            for index, entry in enumerate(tide_list):
                if entry[0] == update_time:
                    tide_list[index][2] = update_trend
        return tide_list