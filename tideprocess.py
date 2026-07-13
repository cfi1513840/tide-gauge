class ProcTide:
    """
    Process tide data and set high and low tide tags.
    The __init__ method analyzes the previous 24 hours of
    tide measurements to detect the high and low tide events.
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
