from math import sqrt, log10

class WelfordRunningVariance(object):
    """
    Python implentation of Welford's running variance algorithm
    http://www.johndcook.com/standard_deviation.html
    """
    def __init__(self):
        self._count = 0
        self._mean = None
        self._last_mean = None
        self._max = None
        self._min = None
        self._sum = None

        self._s = None
        self._last_s = None

        
    def send(self, value):
        self._count += 1
        
        if self._count == 1:
            self._mean = value
            self._max = value
            self._min = value
            self._sum = value
            self._last_mean = value
            self._last_s = 0.0

        else:
            self._mean = self._last_mean + (value - self._last_mean)/self._count
            self._s = self._last_s + (value - self._last_mean) * (value - self._mean)

            self._sum += value
            # check & update max/min values if necessary
            if value > self._max:
                self._max = value
            if value < self._min:
                self._min = value
            
            # prepare for next iteration
            self._last_mean = self._mean
            self._last_s = self._s

            
    def next(self):
        """
        Mimmicing generator function
        """
        return self._mean
    
    def count(self):
        return self._count
            
    def mean(self):
        return self._mean

    def max(self):
        return self._max

    def min(self):
        return self._min

    def sum(self):
        return self._sum
        
    def var(self):
        result = 0
        if self._count >= 2:
            result = self._s/(self._count - 1)
        return result
    
    def stddev(self):
        return sqrt(self.var())


class WelfordRunningVariancedB(object):
    """
    Python implentation of Welford's running variance algorithm (for dB calc)
    http://www.johndcook.com/standard_deviation.html
    """
    def __init__(self):
        self._count = 0
        self._mean = None
        self._last_mean = None

        self._s = None
        self._last_s = None


    def send(self, v):
        value =  10**(v/10.0)
        self._count += 1

        if self._count == 1:
            self._mean = value
            self._last_mean = value
            self._last_s = 0.0
        else:
            self._mean = self._last_mean + (value - self._last_mean)/self._count
            self._s = self._last_s + (value - self._last_mean) * (value - self._mean)

            # prepare for next iteration
            self._last_mean = self._mean
            self._last_s = self._s

    def mean_db(self, as_db=False):
        result = self._mean
        if as_db:
            result =  10 * log10(result)
        return result

    def count(self):
        return self._count

    def var_db(self, as_db=False):
        result = 0
        if self._count >= 2:
            result = self._s/(self._count - 1)

        if as_db:
            result =  10 * log10(result)

        return result

    def next(self):
        """
        Mimmicing generator function
        """
        return self._mean


    def stddev_db(self):
        lin_stdev = sqrt(self.var_db())
        db_stdev =   10 * log10(lin_stdev)
        return db_stdev #WARNING -- this value doesn't seem to make sense
