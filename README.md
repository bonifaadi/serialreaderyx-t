# Serial Reader for y=x(t)

> [!IMPORTANT]
> This project was created to support research that requires data from sensors. This might be discontinued soon.

This program was built for reading COM Seral which has this format and display it as plot with matplotlib

~~~
x, y1, y2, y3, ...
~~~

This program creates

~~~
Pengambilan data dimulai pada <date>

waktu (ms), MAX31855_1, MAX31855_2, MAX6675_1, MAX6675_2, MAX6675_3
~~~

on its 2 first lines by default.
