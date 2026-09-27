from datetime import datetime


def gregorian_to_jalali(gregorian_date: datetime) -> tuple[int,int,int]:
    gy,gm,gd=gregorian_date.year,gregorian_date.month,gregorian_date.day
    g_d_m=[0,31,59,90,120,151,181,212,243,273,304,334]
    gy2=gy+1 if gm>2 else gy
    days=355666+365*gy+((gy2+3)//4)-((gy2+99)//100)+((gy2+399)//400)+gd+g_d_m[gm-1]
    jy=-1595+33*(days//12053); days%=12053
    jy+=4*(days//1461); days%=1461
    if days>365:
        jy+=(days-1)//365; days=(days-1)%365
    jm=days//31+1 if days<186 else (days-186)//30+7
    jd=days%31+1 if days<186 else (days-186)%30+1
    return jy,jm,jd

def format_jalali(value: datetime) -> str:
    y,m,d=gregorian_to_jalali(value)
    return f"{y:04d}/{m:02d}/{d:02d}"
