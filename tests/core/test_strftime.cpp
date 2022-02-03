// Copyright 2017 The Emscripten Authors.  All rights reserved.
// Emscripten is available under two separate licenses, the MIT license and the
// University of Illinois/NCSA Open Source License.  Both these licenses can be
// found in the LICENSE file.

#include <time.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void test(int result, const char* comment, const char* parsed = "") {
  printf("%s: %d\n", comment, result);
  if (!result) {
    printf("\nERROR: %s (\"%s\")\n", comment, parsed);
    abort();
  }
}

int cmp(const char* s1, const char* s2) {
  for (; *s1 == *s2; s1++, s2++) {
    if (*s1 == '\0') break;
  }

  return (*s1 - *s2);
}

int main() {
  struct tm tm;
  char s[1000];
  size_t size;

  // Ensure all fields of `tm` are initialized correctly
  // before we start messing with them.
  time_t t = 0;
  gmtime_r(&t, &tm);

  tm.tm_sec = 4;
  tm.tm_min = 23;
  tm.tm_hour = 20;
  tm.tm_mday = 21;
  tm.tm_mon = 1;
  tm.tm_year = 74;
  tm.tm_wday = 4;
  tm.tm_yday = 51;
  tm.tm_isdst = 0;

  // Test %% escaping
  const char *fmt = "%%H=%H %%M=%m %%z=%z";
  strftime(s, sizeof(s), fmt, &tm);
  printf("%s -> %s\n", fmt, s);

  size = strftime(s, sizeof(s), "", &tm);
  test((size == 0) && (*s == '\0'), "strftime test #1", s);

  size = strftime(s, sizeof(s), "%a", &tm);
  test((size == 3) && !cmp(s, "Thu"), "strftime test #2", s);

  size = strftime(s, sizeof(s), "%A", &tm);
  test((size == 8) && !cmp(s, "Thursday"), "strftime test #3", s);

  size = strftime(s, sizeof(s), "%b", &tm);
  test((size == 3) && !cmp(s, "Feb"), "strftime test #4", s);

  size = strftime(s, sizeof(s), "%B", &tm);
  test((size == 8) && !cmp(s, "February"), "strftime test #5", s);

  size = strftime(s, sizeof(s), "%d", &tm);
  test((size == 2) && !cmp(s, "21"), "strftime test #6", s);

  size = strftime(s, sizeof(s), "%Od", &tm);
  test((size == 2) && !cmp(s, "21"), "strftime test #6a", s);

  size = strftime(s, sizeof(s), "%H", &tm);
  test((size == 2) && !cmp(s, "20"), "strftime test #7", s);

  size = strftime(s, sizeof(s), "%OH", &tm);
  test((size == 2) && !cmp(s, "20"), "strftime test #7a", s);

  size = strftime(s, sizeof(s), "%I", &tm);
  test((size == 2) && !cmp(s, "08"), "strftime test #8", s);

  size = strftime(s, sizeof(s), "%OI", &tm);
  test((size == 2) && !cmp(s, "08"), "strftime test #8a", s);

  size = strftime(s, sizeof(s), "%j", &tm);
  test((size == 3) && !cmp(s, "052"), "strftime test #9", s);

  size = strftime(s, sizeof(s), "%m", &tm);
  test((size == 2) && !cmp(s, "02"), "strftime test #10", s);

  size = strftime(s, sizeof(s), "%Om", &tm);
  test((size == 2) && !cmp(s, "02"), "strftime test #10a", s);

  size = strftime(s, sizeof(s), "%M", &tm);
  test((size == 2) && !cmp(s, "23"), "strftime test #11", s);

  size = strftime(s, sizeof(s), "%OM", &tm);
  test((size == 2) && !cmp(s, "23"), "strftime test #11a", s);

  size = strftime(s, sizeof(s), "%p", &tm);
  test((size == 2) && !cmp(s, "PM"), "strftime test #12", s);

  size = strftime(s, sizeof(s), "%S", &tm);
  test((size == 2) && !cmp(s, "04"), "strftime test #13", s);

  size = strftime(s, sizeof(s), "%OS", &tm);
  test((size == 2) && !cmp(s, "04"), "strftime test #13a", s);

  size = strftime(s, sizeof(s), "%U", &tm);
  test((size == 2) && !cmp(s, "07"), "strftime test #14", s);

  size = strftime(s, sizeof(s), "%OU", &tm);
  test((size == 2) && !cmp(s, "07"), "strftime test #14a", s);

  size = strftime(s, sizeof(s), "%w", &tm);
  test((size == 1) && !cmp(s, "4"), "strftime test #15", s);

  size = strftime(s, sizeof(s), "%Ow", &tm);
  test((size == 1) && !cmp(s, "4"), "strftime test #15a", s);

  size = strftime(s, sizeof(s), "%W", &tm);
  test((size == 2) && !cmp(s, "07"), "strftime test #16", s);

  size = strftime(s, sizeof(s), "%OW", &tm);
  test((size == 2) && !cmp(s, "07"), "strftime test #16a", s);

  size = strftime(s, sizeof(s), "%y", &tm);
  test((size == 2) && !cmp(s, "74"), "strftime test #17", s);

  size = strftime(s, sizeof(s), "%Oy", &tm);
  test((size == 2) && !cmp(s, "74"), "strftime test #17a", s);

  size = strftime(s, sizeof(s), "%Y", &tm);
  test((size == 4) && !cmp(s, "1974"), "strftime test #18", s);

  size = strftime(s, sizeof(s), "%EY", &tm);
  test((size == 4) && !cmp(s, "1974"), "strftime test #18a", s);

  size = strftime(s, sizeof(s), "%%", &tm);
  test((size == 1) && !cmp(s, "%"), "strftime test #19", s);

  size = strftime(s, sizeof(s), "%Y", &tm);
  test((size == 4) && !cmp(s, "1974"), "strftime test #20", s);

  size = strftime(s, 0, "%Y", &tm);
  test((size == 0), "strftime test #21", s);

  // Reset tm to Jan 1st
  tm.tm_mon = 0;
  tm.tm_mday = 1;
  tm.tm_yday = 0;

  // 1/1/1972 was a Tuesday
  tm.tm_wday = 2;
  size = strftime(s, sizeof(s), "%U", &tm);
  test((size == 2) && !cmp(s, "00"), "strftime test #22", s);

  size = strftime(s, sizeof(s), "%W", &tm);
  test((size == 2) && !cmp(s, "00"), "strftime test #23", s);

  // 1/1/1973 was a Monday and is in CW 1
  tm.tm_year = 73;
  tm.tm_wday = 1;
  size = strftime(s, sizeof(s), "%W", &tm);
  test((size == 2) && !cmp(s, "01"), "strftime test #24", s);

  // 1/1/1978 was a Sunday and is in CW 1
  tm.tm_year = 78;
  tm.tm_wday = 0;
  size = strftime(s, sizeof(s), "%U", &tm);
  test((size == 2) && !cmp(s, "01"), "strftime test #25", s);

  // 2/1/1999 (was a Saturday)
  tm.tm_year = 99;
  tm.tm_yday = 1;
  tm.tm_wday = 6;
  size = strftime(s, sizeof(s), "%G (%V)", &tm);
  test((size == 9) && !cmp(s, "1998 (53)"), "strftime test #26", s);

  size = strftime(s, sizeof(s), "%g", &tm);
  test((size == 2) && !cmp(s, "98"), "strftime test #27", s);

  // 30/12/1997 (was a Tuesday)
  tm.tm_year = 97;
  tm.tm_yday = 363;
  tm.tm_wday = 2;
  size = strftime(s, sizeof(s), "%G (%V)", &tm);
  test((size == 9) && !cmp(s, "1998 (01)"), "strftime test #28", s);

  size = strftime(s, sizeof(s), "%g", &tm);
  test((size == 2) && !cmp(s, "98"), "strftime test #29", s);

  tm.tm_wday = 0;
  size = strftime(s, sizeof(s), "%w", &tm);
  test((size == 1) && !cmp(s, "0"), "strftime test #30", s);
  size = strftime(s, sizeof(s), "%u", &tm);
  test((size == 1) && !cmp(s, "7"), "strftime test #31", s);

  tm.tm_wday = 1;
  size = strftime(s, sizeof(s), "%w", &tm);
  test((size == 1) && !cmp(s, "1"), "strftime test #32", s);
  size = strftime(s, sizeof(s), "%u", &tm);
  test((size == 1) && !cmp(s, "1"), "strftime test #33", s);

  tm.tm_wday = 2;
  size = strftime(s, sizeof(s), "%w", &tm);
  test((size == 1) && !cmp(s, "2"), "strftime test #34", s);
  size = strftime(s, sizeof(s), "%u", &tm);
  test((size == 1) && !cmp(s, "2"), "strftime test #35", s);

  tm.tm_wday = 3;
  size = strftime(s, sizeof(s), "%w", &tm);
  test((size == 1) && !cmp(s, "3"), "strftime test #36", s);
  size = strftime(s, sizeof(s), "%u", &tm);
  test((size == 1) && !cmp(s, "3"), "strftime test #37", s);

  tm.tm_wday = 4;
  size = strftime(s, sizeof(s), "%w", &tm);
  test((size == 1) && !cmp(s, "4"), "strftime test #38", s);
  size = strftime(s, sizeof(s), "%u", &tm);
  test((size == 1) && !cmp(s, "4"), "strftime test #39", s);

  tm.tm_wday = 5;
  size = strftime(s, sizeof(s), "%w", &tm);
  test((size == 1) && !cmp(s, "5"), "strftime test #40", s);
  size = strftime(s, sizeof(s), "%u", &tm);
  test((size == 1) && !cmp(s, "5"), "strftime test #41", s);

  tm.tm_wday = 6;
  size = strftime(s, sizeof(s), "%w", &tm);
  test((size == 1) && !cmp(s, "6"), "strftime test #42", s);
  size = strftime(s, sizeof(s), "%u", &tm);
  test((size == 1) && !cmp(s, "6"), "strftime test #43", s);

  // timezones
  time_t xmas2002 = 1040786563ll;
  time_t summer2002 = 1025528525ll;
  localtime_r(&summer2002, &tm);
  // timegm can modify members of the input struct, so make
  // a copy first.
  struct tm copy = tm;
  int ahead = timegm(&copy) >= summer2002;
  size = strftime(s, sizeof(s), "%z", &tm);
  test((size == 5) && strchr(s, ahead ? '+' : '-'), "strftime zone test #1", s);
  size = strftime(s, sizeof(s), "%Z", &tm);
  test(strcmp(s, tzname[tm.tm_isdst]) == 0, "strftime zone test #2", s);

  localtime_r(&xmas2002, &tm);
  copy = tm;
  ahead = timegm(&copy) >= xmas2002;
  size = strftime(s, sizeof(s), "%z", &tm);
  test((size == 5) && strchr(s, ahead ? '+' : '-'), "strftime zone test #3", s);
  size = strftime(s, sizeof(s), "%Z", &tm);
  test(strcmp(s, tzname[tm.tm_isdst]) == 0, "strftime zone test #4", s);

  // AM/PM
  tm.tm_sec = 0;
  tm.tm_min = 0;

  tm.tm_hour = 0;
  size = strftime(s, sizeof(s), "%I %p", &tm);
  test(!cmp(s, "12 AM"), "strftime test #32", s);

  tm.tm_hour = 12;
  size = strftime(s, sizeof(s), "%I %p", &tm);
  test(!cmp(s, "12 PM"), "strftime test #33", s);

  tm.tm_min = 1;

  tm.tm_hour = 0;
  size = strftime(s, sizeof(s), "%I %M %p", &tm);
  test(!cmp(s, "12 01 AM"), "strftime test #34", s);

  tm.tm_hour = 12;
  size = strftime(s, sizeof(s), "%I %M %p", &tm);
  test(!cmp(s, "12 01 PM"), "strftime test #35", s);

  return 0;
}
