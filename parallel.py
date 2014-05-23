# Allstate Purchase Prediction Challenge
# Author: Alessandro Mariani <alzmcr@yahoo.it>

from time import time
from sklearn import ensemble

import multiprocessing, operator
import pandas as pd, numpy as np

## Pickle FIX for multiprocessing using bound methods
## http://stackoverflow.com/questions/1816958/cant-pickle-type-instancemethod-when-using-pythons-multiprocessing-pool-ma/
from copy_reg import pickle
from types import MethodType
        
def _pickle_method(method):
    func_name = method.im_func.__name__
    obj = method.im_self
    cls = method.im_class
    return _unpickle_method, (func_name, obj, cls)

def _unpickle_method(func_name, obj, cls):
    for cls in cls.mro():
        try:
            func = cls.__dict__[func_name]
        except KeyError:
            pass
        else:
            break
    return func.__get__(obj, cls)

class RandomForestsParallel(object):
    # class used to fit & predict in parallel minimizing memory usage
    rfs = []
    def __init__(self,N,ntree,maxfea,leafsize,N_proc=None):
        self.N = N
        self.ntree = ntree; self.maxfea = maxfea; self.leafsize = leafsize
        self.N_proc = N_proc if N_proc is not None else multiprocessing.cpu_count()-1

        # fix pickling when using bound methods in classes
        pickle(MethodType, _pickle_method, _pickle_method)

    def _parallel_fit(self, rf):
        t = time()
        return rf.fit(self.X,self.y,self.w), (time()-t)/60.

    def _parallel_predict(self, rf):
        return rf.predict(self.X)
    
    def fit(self,X,y,w):
        # fit N random forest in parallel
        self.X = X; self.y = y; self.w = w; self.rfs = []
        print "fitting %i RFs using %i processes..." % (self.N,self.N_proc),

        args = [ensemble.RandomForestClassifier(
            n_estimators=self.ntree, max_features=self.maxfea,
            min_samples_leaf=self.leafsize,random_state=irf,
            compute_importances=1) for irf in range(self.N)]

        if self.N_proc > 1:
            pool = multiprocessing.Pool(self.N_proc)
            for i,(rf,irft) in enumerate(pool.imap(self._parallel_fit,args)):
                self.rfs.append(rf); print "rf#%i %.2fm" % (i,irft),
            pool.terminate()
        else:
            for i,rf in enumerate(args):
                rf,irft = self._parallel_fit(rf)
                self.rfs.append(rf); print "rf#%i %.2fm" % (i,irft),
                
        del self.X,self.y,self.w
        # set the importances of the features
        self.impf = self.calculate_impf(X.columns)
        
    def predict(self,X):
        # predict using all the random forest in self.rfs
        # output: array with shap
        self.X = X
        if self.N_proc > 1:
            pool = multiprocessing.Pool(self.N_proc)
            allpreds = np.array([p for p in pool.imap(self._parallel_predict,self.rfs)]).T
            pool.terminate()
        else:
            allpreds = np.array([self._parallel_predict(rf) for rf in self.rfs]).T
            
        del self.X
        return allpreds

    def calculate_impf(self, feature_names):
        return pd.Series(reduce(operator.add,[rf.feature_importances_ for rf in self.rfs]) / self.N, feature_names)     
