def position_size(cash,entry,stop,risk=.01,cap=.15):
    if entry<=0 or stop>=entry:return 0
    return max(0,min(int((cash*risk)//(entry-stop)),int((cash*cap)//entry)))
