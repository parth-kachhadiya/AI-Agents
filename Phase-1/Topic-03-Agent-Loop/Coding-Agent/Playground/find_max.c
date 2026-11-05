#include <stdio.h>

int main() {
    int a = 10, b = 20, c = 30, d = 40;
    int max;

    max = a;

    if (b > max) max = b;
    if (c > max) max = c;
    if (d > max) max = d;

    printf("Maximum number is: %d\n", max);

    return 0;
}