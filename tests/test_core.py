# coding=utf-8

import glob, hashlib, os, re, shutil, subprocess, sys
import tools.shared
from tools.shared import *
from runner import RunnerCore, path_from_root, checked_sanity, test_modes, get_bullet_library

class T(RunnerCore): # Short name, to make it more fun to use manually on the commandline
  def is_le32(self):
    return not ('i386-pc-linux-gnu' in COMPILER_OPTS or self.env.get('EMCC_LLVM_TARGET') == 'i386-pc-linux-gnu')

  def test_hello_world(self):
      test_path = path_from_root('tests', 'core', 'test_hello_world')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

      assert 'EMSCRIPTEN_GENERATED_FUNCTIONS' not in open(self.in_dir('src.cpp.o.js')).read(), 'must not emit this unneeded internal thing'

  def test_intvars(self):
      if self.emcc_args == None: return self.skip('needs ta2')

      test_path = path_from_root('tests', 'core', 'test_intvars')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_sintvars(self):
      Settings.CORRECT_SIGNS = 1 # Relevant to this test
      Settings.CORRECT_OVERFLOWS = 0 # We should not need overflow correction to get this right

      test_path = path_from_root('tests', 'core', 'test_sintvars')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output, force_c=True)

  def test_i64(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('i64 mode 1 requires ta2')

      src = '''
        #include <stdio.h>
        int main()
        {
          long long a = 0x2b00505c10;
          long long b = a >> 29;
          long long c = a >> 32;
          long long d = a >> 34;
          printf("*%Ld,%Ld,%Ld,%Ld*\\n", a, b, c, d);
          unsigned long long ua = 0x2b00505c10;
          unsigned long long ub = ua >> 29;
          unsigned long long uc = ua >> 32;
          unsigned long long ud = ua >> 34;
          printf("*%Ld,%Ld,%Ld,%Ld*\\n", ua, ub, uc, ud);

          long long x = 0x0000def123450789ULL; // any bigger than this, and we
          long long y = 0x00020ef123456089ULL; // start to run into the double precision limit!
          printf("*%Ld,%Ld,%Ld,%Ld,%Ld*\\n", x, y, x | y, x & y, x ^ y, x >> 2, y << 2);

          printf("*");
          long long z = 13;
          int n = 0;
          while (z > 1) {
            printf("%.2f,", (float)z); // these must be integers!
            z = z >> 1;
            n++;
          }
          printf("*%d*\\n", n);
          return 0;
        }
      '''
      self.do_run(src, '*184688860176,344,43,10*\n*184688860176,344,43,10*\n*245127260211081,579378795077769,808077213656969,16428841631881,791648372025088*\n*13.00,6.00,3.00,*3*')

      src = r'''
        #include <time.h>
        #include <stdio.h>
        #include <stdint.h>

        int64_t returner1() { return 0x0000def123450789ULL; }
        int64_t returner2(int test) {
          while (test > 10) test /= 2; // confuse the compiler so it doesn't eliminate this function
          return test > 5 ? 0x0000def123450123ULL : 0ULL;
        }

        void modifier1(int64_t t) {
          t |= 12;
          printf("m1: %Ld\n", t);
        }
        void modifier2(int64_t &t) {
          t |= 12;
        }

        int truthy() {
          int x = time(0);
          while (x > 10) {
            x |= 7;
            x /= 2;
          }
          return x < 3;
        }

        struct IUB {
           int c;
           long long d;
        };

        IUB iub[] = {
           { 55, 17179869201 },
           { 122, 25769803837 },
        };

        int main(int argc, char **argv)
        {
          int64_t x1 = 0x1234def123450789ULL;
          int64_t x2 = 0x1234def123450788ULL;
          int64_t x3 = 0x1234def123450789ULL;
          printf("*%Ld\n%d,%d,%d,%d,%d\n%d,%d,%d,%d,%d*\n", x1, x1==x2, x1<x2, x1<=x2, x1>x2, x1>=x2, // note: some rounding in the printing!
                                                                x1==x3, x1<x3, x1<=x3, x1>x3, x1>=x3);
          printf("*%Ld*\n", returner1());
          printf("*%Ld*\n", returner2(30));

          uint64_t maxx = -1ULL;
          printf("*%Lu*\n*%Lu*\n", maxx, maxx >> 5);

          // Make sure params are not modified if they shouldn't be
          int64_t t = 123;
          modifier1(t);
          printf("*%Ld*\n", t);
          modifier2(t);
          printf("*%Ld*\n", t);

          // global structs with i64s
          printf("*%d,%Ld*\n*%d,%Ld*\n", iub[0].c, iub[0].d, iub[1].c, iub[1].d);

          // Bitshifts
          {
            int64_t a = -1;
            int64_t b = a >> 29;
            int64_t c = a >> 32;
            int64_t d = a >> 34;
            printf("*%Ld,%Ld,%Ld,%Ld*\n", a, b, c, d);
            uint64_t ua = -1;
            int64_t ub = ua >> 29;
            int64_t uc = ua >> 32;
            int64_t ud = ua >> 34;
            printf("*%Ld,%Ld,%Ld,%Ld*\n", ua, ub, uc, ud);
          }

          // Nonconstant bitshifts
          {
            int64_t a = -1;
            int64_t b = a >> (29 - argc + 1);
            int64_t c = a >> (32 - argc + 1);
            int64_t d = a >> (34 - argc + 1);
            printf("*%Ld,%Ld,%Ld,%Ld*\n", a, b, c, d);
            uint64_t ua = -1;
            int64_t ub = ua >> (29 - argc + 1);
            int64_t uc = ua >> (32 - argc + 1);
            int64_t ud = ua >> (34 - argc + 1);
            printf("*%Ld,%Ld,%Ld,%Ld*\n", ua, ub, uc, ud);
          }

          // Math mixtures with doubles
          {
            uint64_t a = 5;
            double b = 6.8;
            uint64_t c = a * b;
            if (truthy()) printf("*%d,%d,%d*\n", (int)&a, (int)&b, (int)&c); // printing addresses prevents optimizations
            printf("*prod:%llu*\n", c);
          }

          // Basic (rounded, for now) math. Just check compilation.
          int64_t a = 0x1234def123450789ULL;
          a--; if (truthy()) a--; // confuse optimizer
          int64_t b = 0x1234000000450789ULL;
          b++; if (truthy()) b--; // confuse optimizer
          printf("*%Ld,%Ld,%Ld,%Ld*\n",   (a+b)/5000, (a-b)/5000, (a*3)/5000, (a/5)/5000);

          a -= 17; if (truthy()) a += 5; // confuse optimizer
          b -= 17; if (truthy()) b += 121; // confuse optimizer
          printf("*%Lx,%Lx,%Lx,%Lx*\n", b - a, b - a/2, b/2 - a, b - 20);

          if (truthy()) a += 5/b; // confuse optimizer
          if (truthy()) b += 121*(3+a/b); // confuse optimizer
          printf("*%Lx,%Lx,%Lx,%Lx*\n", a - b, a - b/2, a/2 - b, a - 20);

          return 0;
        }
      '''
      self.do_run(src, '*1311918518731868041\n' +
                       '0,0,0,1,1\n' +
                       '1,0,1,0,1*\n' +
                       '*245127260211081*\n' +
                       '*245127260209443*\n' +
                       '*18446744073709551615*\n' +
                       '*576460752303423487*\n' +
                       'm1: 127\n' +
                       '*123*\n' +
                       '*127*\n' +
                       '*55,17179869201*\n' +
                       '*122,25769803837*\n' +
                       '*-1,-1,-1,-1*\n' +
                       '*-1,34359738367,4294967295,1073741823*\n' +
                       '*-1,-1,-1,-1*\n' +
                       '*-1,34359738367,4294967295,1073741823*\n' +
                       '*prod:34*\n' +
                       '*524718382041609,49025451137,787151111239120,52476740749274*\n' +
                       '*ffff210edd000002,91990876ea283be,f6e5210edcdd7c45,1234000000450765*\n' +
                       '*def122fffffe,91adef1232283bb,f6e66f78915d7c42,1234def123450763*\n')

      src = r'''
        #include <stdio.h>
        #include <limits>

        int main()
        {
            long long i,j,k;

            i = 0;
            j = -1,
            k = 1;

            printf( "*\n" );
            printf( "%s\n", i > j ? "Ok": "Fail" );
            printf( "%s\n", k > i ? "Ok": "Fail" );
            printf( "%s\n", k > j ? "Ok": "Fail" );
            printf( "%s\n", i < j ? "Fail": "Ok" );
            printf( "%s\n", k < i ? "Fail": "Ok" );
            printf( "%s\n", k < j ? "Fail": "Ok" );
            printf( "%s\n", (i-j) >= k ? "Ok": "Fail" );
            printf( "%s\n", (i-j) <= k ? "Ok": "Fail" );
            printf( "%s\n", i > std::numeric_limits<long long>::min() ? "Ok": "Fail" );
            printf( "%s\n", i < std::numeric_limits<long long>::max() ? "Ok": "Fail" );
            printf( "*\n" );
        }
      '''

      self.do_run(src, '*\nOk\nOk\nOk\nOk\nOk\nOk\nOk\nOk\nOk\nOk\n*')

      # stuff that also needs sign corrections

      Settings.CORRECT_SIGNS = 1

      src = r'''
        #include <stdio.h>
        #include <stdint.h>

        int main()
        {
          // i32 vs i64
          int32_t small = -1;
          int64_t large = -1;
          printf("*%d*\n", small == large);
          small++;
          printf("*%d*\n", small == large);
          uint32_t usmall = -1;
          uint64_t ularge = -1;
          printf("*%d*\n", usmall == ularge);
          return 0;
        }
      '''

      self.do_run(src, '*1*\n*0*\n*0*\n')

  def test_i64_b(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

      test_path = path_from_root('tests', 'core', 'test_i64_b')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_i64_cmp(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

      test_path = path_from_root('tests', 'core', 'test_i64_cmp')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_i64_cmp2(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

      test_path = path_from_root('tests', 'core', 'test_i64_cmp2')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_i64_double(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

      test_path = path_from_root('tests', 'core', 'test_i64_double')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_i64_umul(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

      test_path = path_from_root('tests', 'core', 'test_i64_umul')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_i64_precise(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

      src = r'''
        #include <inttypes.h>
        #include <stdio.h>

        int main() {
          uint64_t x = 0, y = 0;
          for (int i = 0; i < 64; i++) {
            x += 1ULL << i;
            y += x;
            x /= 3;
            y *= 5;
            printf("unsigned %d: %llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu\n", i, x, y, x+y, x-y, x*y, y ? x/y : 0, x ? y/x : 0, y ? x%y : 0, x ? y%x : 0);
          }
          int64_t x2 = 0, y2 = 0;
          for (int i = 0; i < 64; i++) {
            x2 += 1LL << i;
            y2 += x2;
            x2 /= 3 * (i % 7 ? -1 : 1);
            y2 *= 5 * (i % 2 ? -1 : 1);
            printf("signed %d: %lld,%lld,%lld,%lld,%lld,%lld,%lld,%lld,%lld\n", i, x2, y2, x2+y2, x2-y2, x2*y2, y2 ? x2/y2 : 0, x2 ? y2/x2 : 0, y2 ? x2%y2 : 0, x2 ? y2%x2 : 0);
          }
          return 0;
        }
      '''
      self.do_run(src, open(path_from_root('tests', 'i64_precise.txt')).read())

      # Verify that even if we ask for precision, if it is not needed it is not included
      Settings.PRECISE_I64_MATH = 1
      src = '''
        #include <inttypes.h>
        #include <stdio.h>

        int main(int argc, char **argv) {
          uint64_t x = 2125299906845564, y = 1225891506842664;
          if (argc == 12) {
            x = x >> 1;
            y = y >> 1;
          }
          x = x & 12ULL;
          y = y | 12ULL;
          x = x ^ y;
          x <<= 2;
          y >>= 3;
          printf("*%llu, %llu*\\n", x, y);
        }
      '''
      self.do_run(src, '*4903566027370624, 153236438355333*')
      code = open(os.path.join(self.get_dir(), 'src.cpp.o.js')).read()
      assert 'goog.math.Long' not in code, 'i64 precise math should not have been included if not actually used'

      # But if we force it to be included, it is. First, a case where we don't need it
      Settings.PRECISE_I64_MATH = 2
      self.do_run(open(path_from_root('tests', 'hello_world.c')).read(), 'hello')
      code = open(os.path.join(self.get_dir(), 'src.cpp.o.js')).read()
      assert 'goog.math.Long' in code, 'i64 precise math should be included if forced'

      # and now one where we do
      self.do_run(r'''
        #include <stdio.h>

        int main( int argc, char ** argv )
        {
            unsigned long a = 0x60DD1695U;
            unsigned long b = 0xCA8C4E7BU;
            unsigned long long c = (unsigned long long)a * b;
            printf( "c = %016llx\n", c );

            return 0;
        }
      ''', 'c = 4ca38a6bd2973f97')

  def test_i64_llabs(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')
    Settings.PRECISE_I64_MATH = 2

    test_path = path_from_root('tests', 'core', 'test_i64_llabs')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_i64_zextneg(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

    test_path = path_from_root('tests', 'core', 'test_i64_zextneg')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_i64_7z(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

    test_path = path_from_root('tests', 'core', 'test_i64_7z')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output, ['hallo'])

  def test_i64_i16(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

    test_path = path_from_root('tests', 'core', 'test_i64_i16')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_i64_qdouble(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

    test_path = path_from_root('tests', 'core', 'test_i64_qdouble')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_i64_varargs(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('full i64 stuff only in ta2')

    test_path = path_from_root('tests', 'core', 'test_i64_varargs')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output, 'waka fleefl asdfasdfasdfasdf'.split(' '))

  def test_i32_mul_precise(self):
    if self.emcc_args == None: return self.skip('needs ta2')

    test_path = path_from_root('tests', 'core', 'test_i32_mul_precise')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_i32_mul_semiprecise(self):
    if Settings.ASM_JS: return self.skip('asm is always fully precise')

    Settings.PRECISE_I32_MUL = 0 # we want semiprecise here

    test_path = path_from_root('tests', 'core', 'test_i32_mul_semiprecise')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_i16_emcc_intrinsic(self):
    Settings.CORRECT_SIGNS = 1 # Relevant to this test

    test_path = path_from_root('tests', 'core', 'test_i16_emcc_intrinsic')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_double_i64_conversion(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('needs ta2')

    test_path = path_from_root('tests', 'core', 'test_double_i64_conversion')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_float32_precise(self):
    Settings.PRECISE_F32 = 1

    test_path = path_from_root('tests', 'core', 'test_float32_precise')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_negative_zero(self):
    test_path = path_from_root('tests', 'core', 'test_negative_zero')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_llvm_intrinsics(self):
    if self.emcc_args == None: return self.skip('needs ta2')

    Settings.PRECISE_I64_MATH = 2 # for bswap64

    test_path = path_from_root('tests', 'core', 'test_llvm_intrinsics')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_bswap64(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('needs ta2')

    test_path = path_from_root('tests', 'core', 'test_bswap64')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_sha1(self):
    if self.emcc_args == None: return self.skip('needs ta2')

    self.do_run(open(path_from_root('tests', 'sha1.c')).read(), 'SHA1=15dd99a1991e0b3826fede3deffc1feba42278e6')

  def test_cube2md5(self):
    if self.emcc_args == None: return self.skip('needs emcc')
    self.emcc_args += ['--embed-file', 'cube2md5.txt']
    shutil.copyfile(path_from_root('tests', 'cube2md5.txt'), os.path.join(self.get_dir(), 'cube2md5.txt'))
    self.do_run(open(path_from_root('tests', 'cube2md5.cpp')).read(), open(path_from_root('tests', 'cube2md5.ok')).read())

  def test_cube2hash(self):
    try:
      old_chunk_size = os.environ.get('EMSCRIPT_MAX_CHUNK_SIZE') or ''
      os.environ['EMSCRIPT_MAX_CHUNK_SIZE'] = '1' # test splitting out each function to a chunk in emscripten.py (21 functions here)

      # A good test of i64 math
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('requires ta2 C-style memory aliasing')
      self.do_run('', 'Usage: hashstring <seed>',
                  libraries=self.get_library('cube2hash', ['cube2hash.bc'], configure=None),
                  includes=[path_from_root('tests', 'cube2hash')])

      for text, output in [('fleefl', '892BDB6FD3F62E863D63DA55851700FDE3ACF30204798CE9'),
                           ('fleefl2', 'AA2CC5F96FC9D540CA24FDAF1F71E2942753DB83E8A81B61'),
                           ('64bitisslow', '64D8470573635EC354FEE7B7F87C566FCAF1EFB491041670')]:
        self.do_run('', 'hash value: ' + output, [text], no_build=True)
    finally:
      os.environ['EMSCRIPT_MAX_CHUNK_SIZE'] = old_chunk_size

    assert 'asm1' in test_modes
    if self.run_name == 'asm1':
      assert Settings.RELOOP
      generated = open('src.cpp.o.js').read()
      main = generated[generated.find('function _main'):]
      main = main[:main.find('\n}')]
      num_vars = 0
      for v in re.findall('var [^;]+;', main):
        num_vars += v.count(',') + 1
      assert num_vars == 10, 'no variable elimination should have been run, but seeing %d' % num_vars

  def test_unaligned(self):
      if Settings.QUANTUM_SIZE == 1: return self.skip('No meaning to unaligned addresses in q1')

      src = r'''
        #include<stdio.h>

        struct S {
          double x;
          int y;
        };

        int main() {
          // the 64-bit value here will not be 8-byte aligned
          S s0[3] = { {0x12a751f430142, 22}, {0x17a5c85bad144, 98}, {1, 1}};
          char buffer[10*sizeof(S)];
          int b = int(buffer);
          S *s = (S*)(b + 4-b%8);
          s[0] = s0[0];
          s[1] = s0[1];
          s[2] = s0[2];

          printf("*%d : %d : %d\n", sizeof(S), ((unsigned int)&s[0]) % 8 != ((unsigned int)&s[1]) % 8,
                                               ((unsigned int)&s[1]) - ((unsigned int)&s[0]));
          s[0].x++;
          s[0].y++;
          s[1].x++;
          s[1].y++;
          printf("%.1f,%d,%.1f,%d\n", s[0].x, s[0].y, s[1].x, s[1].y);
          return 0;
        }
        '''

      # TODO: A version of this with int64s as well

      if self.is_le32():
        return self.skip('LLVM marks the reads of s as fully aligned, making this test invalid')
      else:
        self.do_run(src, '*12 : 1 : 12\n328157500735811.0,23,416012775903557.0,99\n')

      return # TODO: continue to the next part here

      # Test for undefined behavior in C. This is not legitimate code, but does exist

      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('No meaning to unaligned addresses without t2')

      src = r'''
        #include <stdio.h>

        int main()
        {
          int x[10];
          char *p = (char*)&x[0];
          p++;
          short *q = (short*)p;
          *q = 300;
          printf("*%d:%d*\n", *q, ((int)q)%2);
          int *r = (int*)p;
          *r = 515559;
          printf("*%d*\n", *r);
          long long *t = (long long*)p;
          *t = 42949672960;
          printf("*%Ld*\n", *t);
          return 0;
        }
      '''

      try:
        self.do_run(src, '*300:1*\n*515559*\n*42949672960*\n')
      except Exception, e:
        assert 'must be aligned' in str(e), e # expected to fail without emulation

  def test_align64(self):
    src = r'''
      #include <stdio.h>

      // inspired by poppler

      enum Type {
        A = 10,
        B = 20
      };

      struct Object {
        Type type;
        union {
          int intg;
          double real;
          char *name;
        };
      };

      struct Principal {
        double x;
        Object a;
        double y;
      };

      int main(int argc, char **argv)
      {
        int base = argc-1;
        Object *o = NULL;
        printf("%d,%d\n", sizeof(Object), sizeof(Principal));
        printf("%d,%d,%d,%d\n", (int)&o[base].type, (int)&o[base].intg, (int)&o[base].real, (int)&o[base].name);
        printf("%d,%d,%d,%d\n", (int)&o[base+1].type, (int)&o[base+1].intg, (int)&o[base+1].real, (int)&o[base+1].name);
        Principal p, q;
        p.x = p.y = q.x = q.y = 0;
        p.a.type = A;
        p.a.real = 123.456;
        *(&q.a) = p.a;
        printf("%.2f,%d,%.2f,%.2f : %.2f,%d,%.2f,%.2f\n", p.x, p.a.type, p.a.real, p.y, q.x, q.a.type, q.a.real, q.y);
        return 0;
      }
    '''

    if self.is_le32():
      self.do_run(src, '''16,32
0,8,8,8
16,24,24,24
0.00,10,123.46,0.00 : 0.00,10,123.46,0.00
''')
    else:
      self.do_run(src, '''12,28
0,4,4,4
12,16,16,16
0.00,10,123.46,0.00 : 0.00,10,123.46,0.00
''')

  def test_unsigned(self):
      Settings.CORRECT_SIGNS = 1 # We test for exactly this sort of thing here
      Settings.CHECK_SIGNS = 0
      src = '''
        #include <stdio.h>
        const signed char cvals[2] = { -1, -2 }; // compiler can store this is a string, so -1 becomes \FF, and needs re-signing
        int main()
        {
          {
            unsigned char x = 200;
            printf("*%d*\\n", x);
            unsigned char y = -22;
            printf("*%d*\\n", y);
          }

          int varey = 100;
          unsigned int MAXEY = -1, MAXEY2 = -77;
          printf("*%u,%d,%u*\\n", MAXEY, varey >= MAXEY, MAXEY2); // 100 >= -1? not in unsigned!

          int y = cvals[0];
          printf("*%d,%d,%d,%d*\\n", cvals[0], cvals[0] < 0, y, y < 0);
          y = cvals[1];
          printf("*%d,%d,%d,%d*\\n", cvals[1], cvals[1] < 0, y, y < 0);

          // zext issue - see mathop in jsifier
          unsigned char x8 = -10;
          unsigned long hold = 0;
          hold += x8;
          int y32 = hold+50;
          printf("*%u,%u*\\n", hold, y32);

          // Comparisons
          x8 = 0;
          for (int i = 0; i < 254; i++) x8++; // make it an actual 254 in JS - not a -2
          printf("*%d,%d*\\n", x8+1 == 0xff, x8+1 != 0xff); // 0xff may be '-1' in the bitcode

          return 0;
        }
      '''
      self.do_run(src, '*4294967295,0,4294967219*\n*-1,1,-1,1*\n*-2,1,-2,1*\n*246,296*\n*1,0*')

      # Now let's see some code that should just work in USE_TYPED_ARRAYS == 2, but requires
      # corrections otherwise
      if Settings.USE_TYPED_ARRAYS == 2:
        Settings.CORRECT_SIGNS = 0
        Settings.CHECK_SIGNS = 1 if not Settings.ASM_JS else 0
      else:
        Settings.CORRECT_SIGNS = 1
        Settings.CHECK_SIGNS = 0

      src = '''
        #include <stdio.h>
        int main()
        {
          {
            unsigned char x;
            unsigned char *y = &x;
            *y = -1;
            printf("*%d*\\n", x);
          }
          {
            unsigned short x;
            unsigned short *y = &x;
            *y = -1;
            printf("*%d*\\n", x);
          }
          /*{ // This case is not checked. The hint for unsignedness is just the %u in printf, and we do not analyze that
            unsigned int x;
            unsigned int *y = &x;
            *y = -1;
            printf("*%u*\\n", x);
          }*/
          {
            char x;
            char *y = &x;
            *y = 255;
            printf("*%d*\\n", x);
          }
          {
            char x;
            char *y = &x;
            *y = 65535;
            printf("*%d*\\n", x);
          }
          {
            char x;
            char *y = &x;
            *y = 0xffffffff;
            printf("*%d*\\n", x);
          }
          return 0;
        }
      '''
      self.do_run(src, '*255*\n*65535*\n*-1*\n*-1*\n*-1*')

  def test_bitfields(self):
      if self.emcc_args is None: Settings.SAFE_HEAP = 0 # bitfields do loads on invalid areas, by design

      test_path = path_from_root('tests', 'core', 'test_bitfields')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_floatvars(self):
    test_path = path_from_root('tests', 'core', 'test_floatvars')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_fast_math(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    Building.COMPILER_TEST_OPTS += ['-ffast-math']

    test_path = path_from_root('tests', 'core', 'test_fast_math')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output, ['5', '6', '8'])

  def test_zerodiv(self):
    test_path = path_from_root('tests', 'core', 'test_zerodiv')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_zero_multiplication(self):
    test_path = path_from_root('tests', 'core', 'test_zero_multiplication')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_isnan(self):
    test_path = path_from_root('tests', 'core', 'test_isnan')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_globaldoubles(self):
    test_path = path_from_root('tests', 'core', 'test_globaldoubles')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_math(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('requires ta2')

      test_path = path_from_root('tests', 'core', 'test_math')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_erf(self):
      test_path = path_from_root('tests', 'core', 'test_erf')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_math_hyperbolic(self):
      src = open(path_from_root('tests', 'hyperbolic', 'src.c'), 'r').read()
      expected = open(path_from_root('tests', 'hyperbolic', 'output.txt'), 'r').read()
      self.do_run(src, expected)

  def test_frexp(self):
      test_path = path_from_root('tests', 'core', 'test_frexp')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_rounding(self):
      test_path = path_from_root('tests', 'core', 'test_rounding')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_fcvt(self):
      if self.emcc_args is None: return self.skip('requires emcc')

      test_path = path_from_root('tests', 'core', 'test_fcvt')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_llrint(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('requires ta2')

    test_path = path_from_root('tests', 'core', 'test_llrint')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_getgep(self):
    # Generated code includes getelementptr (getelementptr, 0, 1), i.e., GEP as the first param to GEP
    test_path = path_from_root('tests', 'core', 'test_getgep')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_multiply_defined_symbols(self):
    a1 = "int f() { return 1; }"
    a1_name = os.path.join(self.get_dir(), 'a1.c')
    open(a1_name, 'w').write(a1)
    a2 = "void x() {}"
    a2_name = os.path.join(self.get_dir(), 'a2.c')
    open(a2_name, 'w').write(a2)
    b1 = "int f() { return 2; }"
    b1_name = os.path.join(self.get_dir(), 'b1.c')
    open(b1_name, 'w').write(b1)
    b2 = "void y() {}"
    b2_name = os.path.join(self.get_dir(), 'b2.c')
    open(b2_name, 'w').write(b2)
    main = r'''
      #include <stdio.h>
      int f();
      int main() {
        printf("result: %d\n", f());
        return 0;
      }
    '''
    main_name = os.path.join(self.get_dir(), 'main.c')
    open(main_name, 'w').write(main)

    Building.emcc(a1_name)
    Building.emcc(a2_name)
    Building.emcc(b1_name)
    Building.emcc(b2_name)
    Building.emcc(main_name)

    liba_name = os.path.join(self.get_dir(), 'liba.a')
    Building.emar('cr', liba_name, [a1_name + '.o', a2_name + '.o'])
    libb_name = os.path.join(self.get_dir(), 'libb.a')
    Building.emar('cr', libb_name, [b1_name + '.o', b2_name + '.o'])

    all_name = os.path.join(self.get_dir(), 'all.bc')
    Building.link([main_name + '.o', liba_name, libb_name], all_name)

    self.do_ll_run(all_name, 'result: 1')

  def test_if(self):
    test_path = path_from_root('tests', 'core', 'test_if')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_if_else(self):
    test_path = path_from_root('tests', 'core', 'test_if_else')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_loop(self):
    test_path = path_from_root('tests', 'core', 'test_loop')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_stack(self):
    Settings.INLINING_LIMIT = 50

    test_path = path_from_root('tests', 'core', 'test_stack')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strings(self):
      test_path = path_from_root('tests', 'core', 'test_strings')
      src, output = (test_path + s for s in ('.in', '.out'))

      for named in (0, 1):
        print named

        Settings.NAMED_GLOBALS = named
        self.do_run_from_file(src, output, ['wowie', 'too', '74'])

        if self.emcc_args == []:
          gen = open(self.in_dir('src.cpp.o.js')).read()
          assert ('var __str1;' in gen) == named

  def test_strcmp_uni(self):
    test_path = path_from_root('tests', 'core', 'test_strcmp_uni')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strndup(self):
    test_path = path_from_root('tests', 'core', 'test_strndup')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_errar(self):
    test_path = path_from_root('tests', 'core', 'test_errar')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_mainenv(self):
    test_path = path_from_root('tests', 'core', 'test_mainenv')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_funcs(self):
    test_path = path_from_root('tests', 'core', 'test_funcs')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_structs(self):
    test_path = path_from_root('tests', 'core', 'test_structs')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  gen_struct_src = '''
        #include <stdio.h>
        #include <stdlib.h>
        #include "emscripten.h"

        struct S
        {
          int x, y;
        };
        int main()
        {
          S* a = {{gen_struct}};
          a->x = 51; a->y = 62;
          printf("*%d,%d*\\n", a->x, a->y);
          {{del_struct}}(a);
          return 0;
        }
  '''

  def test_mallocstruct(self):
      self.do_run(self.gen_struct_src.replace('{{gen_struct}}', '(S*)malloc(sizeof(S))').replace('{{del_struct}}', 'free'), '*51,62*')

  def test_newstruct(self):
      if self.emcc_args is None: return self.skip('requires emcc')
      self.do_run(self.gen_struct_src.replace('{{gen_struct}}', 'new S').replace('{{del_struct}}', 'delete'), '*51,62*')

  def test_addr_of_stacked(self):
    test_path = path_from_root('tests', 'core', 'test_addr_of_stacked')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_globals(self):
    test_path = path_from_root('tests', 'core', 'test_globals')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_linked_list(self):
    test_path = path_from_root('tests', 'core', 'test_linked_list')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_sup(self):
      src = '''
        #include <stdio.h>

        struct S4   { int x;          }; // size: 4
        struct S4_2 { short x, y;     }; // size: 4, but for alignment purposes, 2
        struct S6   { short x, y, z;  }; // size: 6
        struct S6w  { char x[6];      }; // size: 6 also
        struct S6z  { int x; short y; }; // size: 8, since we align to a multiple of the biggest - 4

        struct C___  { S6 a, b, c; int later; };
        struct Carr  { S6 a[3]; int later; }; // essentially the same, but differently defined
        struct C__w  { S6 a; S6w b; S6 c; int later; }; // same size, different struct
        struct Cp1_  { int pre; short a; S6 b, c; int later; }; // fillers for a
        struct Cp2_  { int a; short pre; S6 b, c; int later; }; // fillers for a (get addr of the other filler)
        struct Cint  { S6 a; int  b; S6 c; int later; }; // An int (different size) for b
        struct C4__  { S6 a; S4   b; S6 c; int later; }; // Same size as int from before, but a struct
        struct C4_2  { S6 a; S4_2 b; S6 c; int later; }; // Same size as int from before, but a struct with max element size 2
        struct C__z  { S6 a; S6z  b; S6 c; int later; }; // different size, 8 instead of 6

        int main()
        {
          #define TEST(struc) \\
          { \\
            struc *s = 0; \\
            printf("*%s: %d,%d,%d,%d<%d*\\n", #struc, (int)&(s->a), (int)&(s->b), (int)&(s->c), (int)&(s->later), sizeof(struc)); \\
          }
          #define TEST_ARR(struc) \\
          { \\
            struc *s = 0; \\
            printf("*%s: %d,%d,%d,%d<%d*\\n", #struc, (int)&(s->a[0]), (int)&(s->a[1]), (int)&(s->a[2]), (int)&(s->later), sizeof(struc)); \\
          }
          printf("sizeofs:%d,%d\\n", sizeof(S6), sizeof(S6z));
          TEST(C___);
          TEST_ARR(Carr);
          TEST(C__w);
          TEST(Cp1_);
          TEST(Cp2_);
          TEST(Cint);
          TEST(C4__);
          TEST(C4_2);
          TEST(C__z);
          return 0;
        }
      '''
      if Settings.QUANTUM_SIZE == 1:
        self.do_run(src, 'sizeofs:6,8\n*C___: 0,3,6,9<24*\n*Carr: 0,3,6,9<24*\n*C__w: 0,3,9,12<24*\n*Cp1_: 1,2,5,8<24*\n*Cp2_: 0,2,5,8<24*\n*Cint: 0,3,4,7<24*\n*C4__: 0,3,4,7<24*\n*C4_2: 0,3,5,8<20*\n*C__z: 0,3,5,8<28*')
      else:
        self.do_run(src, 'sizeofs:6,8\n*C___: 0,6,12,20<24*\n*Carr: 0,6,12,20<24*\n*C__w: 0,6,12,20<24*\n*Cp1_: 4,6,12,20<24*\n*Cp2_: 0,6,12,20<24*\n*Cint: 0,8,12,20<24*\n*C4__: 0,8,12,20<24*\n*C4_2: 0,6,10,16<20*\n*C__z: 0,8,16,24<28*')

  def test_assert(self):
    test_path = path_from_root('tests', 'core', 'test_assert')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_libcextra(self):
      if self.emcc_args is None: return self.skip('needs emcc for libcextra')

      test_path = path_from_root('tests', 'core', 'test_libcextra')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_regex(self):
      if self.emcc_args is None: return self.skip('needs emcc for libcextra')

      test_path = path_from_root('tests', 'core', 'test_regex')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_longjmp(self):
      test_path = path_from_root('tests', 'core', 'test_longjmp')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_longjmp2(self):
    test_path = path_from_root('tests', 'core', 'test_longjmp2')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_longjmp3(self):
    test_path = path_from_root('tests', 'core', 'test_longjmp3')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_longjmp4(self):
    test_path = path_from_root('tests', 'core', 'test_longjmp4')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_longjmp_funcptr(self):
    test_path = path_from_root('tests', 'core', 'test_longjmp_funcptr')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_longjmp_repeat(self):
      Settings.MAX_SETJMPS = 1

      test_path = path_from_root('tests', 'core', 'test_longjmp_repeat')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_longjmp_stacked(self):
    test_path = path_from_root('tests', 'core', 'test_longjmp_stacked')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)


  def test_longjmp_exc(self):
    test_path = path_from_root('tests', 'core', 'test_longjmp_exc')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_setjmp_many(self):
    src = r'''
      #include <stdio.h>
      #include <setjmp.h>

      int main(int argc) {
        jmp_buf buf;
        for (int i = 0; i < NUM; i++) printf("%d\n", setjmp(buf));
        if (argc-- == 1131) longjmp(buf, 11);
        return 0;
      }
    '''
    for num in [Settings.MAX_SETJMPS, Settings.MAX_SETJMPS+1]:
      print num
      self.do_run(src.replace('NUM', str(num)), '0\n' * num if num <= Settings.MAX_SETJMPS or not Settings.ASM_JS else 'build with a higher value for MAX_SETJMPS')

  def test_exceptions(self):
      if Settings.QUANTUM_SIZE == 1: return self.skip("we don't support libcxx in q1")
      if self.emcc_args is None: return self.skip('need emcc to add in libcxx properly')

      Settings.EXCEPTION_DEBUG = 1

      Settings.DISABLE_EXCEPTION_CATCHING = 0
      if '-O2' in self.emcc_args:
        self.emcc_args += ['--closure', '1'] # Use closure here for some additional coverage

      src = '''
        #include <stdio.h>
        void thrower() {
          printf("infunc...");
          throw(99);
          printf("FAIL");
        }
        int main() {
          try {
            printf("*throw...");
            throw(1);
            printf("FAIL");
          } catch(...) {
            printf("caught!");
          }
          try {
            thrower();
          } catch(...) {
            printf("done!*\\n");
          }
          return 0;
        }
      '''
      self.do_run(src, '*throw...caught!infunc...done!*')

      Settings.DISABLE_EXCEPTION_CATCHING = 1
      self.do_run(src, 'Exception catching is disabled, this exception cannot be caught. Compile with -s DISABLE_EXCEPTION_CATCHING=0')

      src = '''
      #include <iostream>

      class MyException
      {
      public:
          MyException(){ std::cout << "Construct..."; }
          MyException( const MyException & ) { std::cout << "Copy..."; }
          ~MyException(){ std::cout << "Destruct..."; }
      };

      int function()
      {
          std::cout << "Throw...";
          throw MyException();
      }

      int function2()
      {
          return function();
      }

      int main()
      {
          try
          {
              function2();
          }
          catch (MyException & e)
          {
              std::cout << "Catched...";
          }

          try
          {
              function2();
          }
          catch (MyException e)
          {
              std::cout << "Catched...";
          }

          return 0;
      }
      '''

      Settings.DISABLE_EXCEPTION_CATCHING = 0
      if '-O2' in self.emcc_args:
        self.emcc_args.pop() ; self.emcc_args.pop() # disable closure to work around a closure bug
      self.do_run(src, 'Throw...Construct...Catched...Destruct...Throw...Construct...Copy...Catched...Destruct...Destruct...')

  def test_exception_2(self):
    if self.emcc_args is None: return self.skip('need emcc to add in libcxx properly')
    Settings.DISABLE_EXCEPTION_CATCHING = 0

    test_path = path_from_root('tests', 'core', 'test_exception_2')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_white_list_exception(self):
    Settings.DISABLE_EXCEPTION_CATCHING = 2
    Settings.EXCEPTION_CATCHING_WHITELIST = ["__Z12somefunctionv"]
    Settings.INLINING_LIMIT = 50 # otherwise it is inlined and not identified

    test_path = path_from_root('tests', 'core', 'test_white_list_exception')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

    Settings.DISABLE_EXCEPTION_CATCHING = 0
    Settings.EXCEPTION_CATCHING_WHITELIST = []

  def test_uncaught_exception(self):
      if self.emcc_args is None: return self.skip('no libcxx inclusion without emcc')

      Settings.DISABLE_EXCEPTION_CATCHING = 0

      src = r'''
        #include <stdio.h>
        #include <exception>
        struct X {
          ~X() {
            printf("exception? %s\n", std::uncaught_exception() ? "yes" : "no");
          }
        };
        int main() {
          printf("exception? %s\n", std::uncaught_exception() ? "yes" : "no");
          try {
            X x;
            throw 1;
          } catch(...) {
            printf("exception? %s\n", std::uncaught_exception() ? "yes" : "no");
          }
          printf("exception? %s\n", std::uncaught_exception() ? "yes" : "no");
          return 0;
        }
      '''
      self.do_run(src, 'exception? no\nexception? yes\nexception? no\nexception? no\n')

      src = r'''
        #include <fstream>
        #include <iostream>
        int main() {
          std::ofstream os("test");
          os << std::unitbuf << "foo"; // trigger a call to std::uncaught_exception from
                                       // std::basic_ostream::sentry::~sentry
          std::cout << "success";
        }
      '''
      self.do_run(src, 'success')

  def test_typed_exceptions(self):
      Settings.DISABLE_EXCEPTION_CATCHING = 0
      Settings.SAFE_HEAP = 0  # Throwing null will cause an ignorable null pointer access.
      src = open(path_from_root('tests', 'exceptions', 'typed.cpp'), 'r').read()
      expected = open(path_from_root('tests', 'exceptions', 'output.txt'), 'r').read()
      self.do_run(src, expected)

  def test_multiexception(self):
    Settings.DISABLE_EXCEPTION_CATCHING = 0

    test_path = path_from_root('tests', 'core', 'test_multiexception')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_std_exception(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    Settings.DISABLE_EXCEPTION_CATCHING = 0
    self.emcc_args += ['-s', 'SAFE_HEAP=0']

    test_path = path_from_root('tests', 'core', 'test_std_exception')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_async_exit(self):
    open('main.c', 'w').write(r'''
      #include <stdio.h>
      #include <stdlib.h>
      #include "emscripten.h"

      void main_loop() {
        exit(EXIT_SUCCESS);
      }

      int main() {
        emscripten_set_main_loop(main_loop, 60, 0);
        return 0;
      }
    ''')

    Popen([PYTHON, EMCC, 'main.c']).communicate()
    self.assertNotContained('Reached an unreachable!', run_js(self.in_dir('a.out.js'), stderr=STDOUT))

  def test_exit_stack(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    if Settings.ASM_JS: return self.skip('uses report_stack without exporting')

    Settings.INLINING_LIMIT = 50

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      extern "C" {
        extern void report_stack(int x);
      }

      char moar() {
        char temp[125];
        for (int i = 0; i < 125; i++) temp[i] = i*i;
        for (int i = 1; i < 125; i++) temp[i] += temp[i-1]/2;
        if (temp[100] != 99) exit(1);
        return temp[120];
      }

      int main(int argc, char *argv[]) {
        report_stack((int)alloca(4));
        printf("*%d*\n", moar());
        return 0;
      }
    '''

    open(os.path.join(self.get_dir(), 'pre.js'), 'w').write('''
      var initialStack = -1;
      var _report_stack = function(x) {
        Module.print('reported');
        initialStack = x;
      }
      var Module = {
        postRun: function() {
          Module.print('Exit Status: ' + EXITSTATUS);
          Module.print('postRun');
          assert(initialStack == STACKTOP, [initialStack, STACKTOP]);
          Module.print('ok.');
        }
      };
    ''')

    self.emcc_args += ['--pre-js', 'pre.js']
    self.do_run(src, '''reported\nExit Status: 1\npostRun\nok.\n''')

  def test_class(self):
    test_path = path_from_root('tests', 'core', 'test_class')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_inherit(self):
    test_path = path_from_root('tests', 'core', 'test_inherit')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_isdigit_l(self):
      if self.emcc_args is None: return self.skip('no libcxx inclusion without emcc')

      test_path = path_from_root('tests', 'core', 'test_isdigit_l')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_iswdigit(self):
      if self.emcc_args is None: return self.skip('no libcxx inclusion without emcc')

      test_path = path_from_root('tests', 'core', 'test_iswdigit')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_polymorph(self):
      if self.emcc_args is None: return self.skip('requires emcc')

      test_path = path_from_root('tests', 'core', 'test_polymorph')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_segfault(self):
    if self.emcc_args is None: return self.skip('SAFE_HEAP without ta2 means we check types too, which hide segfaults')
    if Settings.ASM_JS: return self.skip('asm does not support safe heap')

    Settings.SAFE_HEAP = 1

    for addr in ['0', 'new D2()']:
      print addr
      src = r'''
        #include <stdio.h>

        struct Classey {
          virtual void doIt() = 0;
        };

        struct D1 : Classey {
          virtual void doIt() { printf("fleefl\n"); }
        };

        struct D2 : Classey {
          virtual void doIt() { printf("marfoosh\n"); }
        };

        int main(int argc, char **argv)
        {
          Classey *p = argc == 100 ? new D1() : (Classey*)%s;

          p->doIt();

          return 0;
        }
      ''' % addr
      self.do_run(src, 'segmentation fault' if addr.isdigit() else 'marfoosh')

  def test_safe_dyncalls(self):
    if Settings.ASM_JS: return self.skip('asm does not support missing function stack traces')
    if Settings.SAFE_HEAP: return self.skip('safe heap warning will appear instead')
    if self.emcc_args is None: return self.skip('need libc')

    Settings.SAFE_DYNCALLS = 1

    for cond, body, work in [(True, True, False), (True, False, False), (False, True, True), (False, False, False)]:
      print cond, body, work
      src = r'''
        #include <stdio.h>

        struct Classey {
          virtual void doIt() = 0;
        };

        struct D1 : Classey {
          virtual void doIt() BODY;
        };

        int main(int argc, char **argv)
        {
          Classey *p = argc COND 100 ? new D1() : NULL;
          printf("%p\n", p);
          p->doIt();

          return 0;
        }
      '''.replace('COND', '==' if cond else '!=').replace('BODY', r'{ printf("all good\n"); }' if body else '')
      self.do_run(src, 'dyncall error: vi' if not work else 'all good')

  def test_dynamic_cast(self):
      if self.emcc_args is None: return self.skip('need libcxxabi')

      test_path = path_from_root('tests', 'core', 'test_dynamic_cast')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_dynamic_cast_b(self):
      if self.emcc_args is None: return self.skip('need libcxxabi')

      test_path = path_from_root('tests', 'core', 'test_dynamic_cast_b')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_dynamic_cast_2(self):
    if self.emcc_args is None: return self.skip('need libcxxabi')

    test_path = path_from_root('tests', 'core', 'test_dynamic_cast_2')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_funcptr(self):
    test_path = path_from_root('tests', 'core', 'test_funcptr')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_mathfuncptr(self):
    test_path = path_from_root('tests', 'core', 'test_mathfuncptr')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_funcptrfunc(self):
    test_path = path_from_root('tests', 'core', 'test_funcptrfunc')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_funcptr_namecollide(self):
    test_path = path_from_root('tests', 'core', 'test_funcptr_namecollide')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output, force_c=True)

  def test_emptyclass(self):
      if self.emcc_args is None: return self.skip('requires emcc')

      test_path = path_from_root('tests', 'core', 'test_emptyclass')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_alloca(self):
    test_path = path_from_root('tests', 'core', 'test_alloca')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output, force_c=True)

  def test_rename(self):
    src = open(path_from_root('tests', 'stdio', 'test_rename.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_alloca_stack(self):
    if self.emcc_args is None: return # too slow in other modes

    test_path = path_from_root('tests', 'core', 'test_alloca_stack')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output, force_c=True)

  def test_stack_byval(self):
    if self.emcc_args is None: return # too slow in other modes

    test_path = path_from_root('tests', 'core', 'test_stack_byval')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_stack_varargs(self):
    if self.emcc_args is None: return # too slow in other modes

    Settings.INLINING_LIMIT = 50
    Settings.TOTAL_STACK = 1024

    test_path = path_from_root('tests', 'core', 'test_stack_varargs')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_stack_varargs2(self):
    if self.emcc_args is None: return # too slow in other modes
    Settings.TOTAL_STACK = 1024
    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      void func(int i) {
      }
      int main() {
        for (int i = 0; i < 1024; i++) {
          printf("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
                   i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i);
        }
        printf("ok!\n");
        return 0;
      }
    '''
    self.do_run(src, 'ok!')

    print 'with return'

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      int main() {
        for (int i = 0; i < 1024; i++) {
          int j = printf("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",
                   i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i);
          printf(" (%d)\n", j);
        }
        printf("ok!\n");
        return 0;
      }
    '''
    self.do_run(src, 'ok!')

    print 'with definitely no return'

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>
      #include <stdarg.h>

      void vary(const char *s, ...)
      {
        va_list v;
        va_start(v, s);
        char d[20];
        vsnprintf(d, 20, s, v);
        puts(d);

        // Try it with copying
        va_list tempva;
        va_copy(tempva, v);
        vsnprintf(d, 20, s, tempva);
        puts(d);

        va_end(v);
      }

      int main() {
        for (int i = 0; i < 1024; i++) {
          int j = printf("%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",
                   i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i, i);
          printf(" (%d)\n", j);
          vary("*cheez: %d+%d*", 99, 24);
          vary("*albeit*");
        }
        printf("ok!\n");
        return 0;
      }
    '''
    self.do_run(src, 'ok!')

  def test_stack_void(self):
    Settings.INLINING_LIMIT = 50

    test_path = path_from_root('tests', 'core', 'test_stack_void')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_life(self):
    if self.emcc_args is None: return self.skip('need c99')
    self.emcc_args += ['-std=c99']
    src = open(path_from_root('tests', 'life.c'), 'r').read()
    self.do_run(src, '''--------------------------------
[]                                    []                  [][][]
                    []  []    []    [][]  []            []  []  
[]                [][]  [][]              [][][]      []        
                  []    []      []      []  [][]    []        []
                  []  [][]    []        []    []  []    [][][][]
                    [][]      [][]  []    [][][]  []        []  
                                []  [][]  [][]    [][]  [][][]  
                                    [][]          [][][]  []  []
                                    [][]              [][]    []
                                                          [][][]
                                                            []  
                                                                
                                                                
                                                                
                                                                
                                        [][][]                  
                                      []      [][]      [][]    
                                      [][]      []  [][]  [][]  
                                                    [][]  [][]  
                                                      []        
                  [][]                                          
                  [][]                                        []
[]                                                      [][]  []
                                                  [][][]      []
                                                []      [][]    
[]                                                    []      []
                                                          []    
[]                                                        []  []
                                              [][][]            
                                                                
                                  []                            
                              [][][]                          []
--------------------------------
''', ['2'], force_c=True)

  def test_array2(self):
    test_path = path_from_root('tests', 'core', 'test_array2')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_array2b(self):
    test_path = path_from_root('tests', 'core', 'test_array2b')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_constglobalstructs(self):
    test_path = path_from_root('tests', 'core', 'test_constglobalstructs')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_conststructs(self):
    test_path = path_from_root('tests', 'core', 'test_conststructs')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_bigarray(self):
    if self.emcc_args is None: return self.skip('need ta2 to compress type data on zeroinitializers')

    test_path = path_from_root('tests', 'core', 'test_bigarray')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_mod_globalstruct(self):
    test_path = path_from_root('tests', 'core', 'test_mod_globalstruct')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_pystruct(self):
      src = '''
        #include <stdio.h>

        // Based on CPython code
        union PyGC_Head {
            struct {
                union PyGC_Head *gc_next;
                union PyGC_Head *gc_prev;
                size_t gc_refs;
            } gc;
            long double dummy;  /* force worst-case alignment */
        } ;

        struct gc_generation {
            PyGC_Head head;
            int threshold; /* collection threshold */
            int count; /* count of allocations or collections of younger
                          generations */
        };

        #define NUM_GENERATIONS 3
        #define GEN_HEAD(n) (&generations[n].head)

        /* linked lists of container objects */
        static struct gc_generation generations[NUM_GENERATIONS] = {
            /* PyGC_Head,                               threshold,      count */
            {{{GEN_HEAD(0), GEN_HEAD(0), 0}},           700,            0},
            {{{GEN_HEAD(1), GEN_HEAD(1), 0}},           10,             0},
            {{{GEN_HEAD(2), GEN_HEAD(2), 0}},           10,             0},
        };

        int main()
        {
          gc_generation *n = NULL;
          printf("*%d,%d,%d,%d,%d,%d,%d,%d*\\n",
            (int)(&n[0]),
            (int)(&n[0].head),
            (int)(&n[0].head.gc.gc_next),
            (int)(&n[0].head.gc.gc_prev),
            (int)(&n[0].head.gc.gc_refs),
            (int)(&n[0].threshold), (int)(&n[0].count), (int)(&n[1])
          );
          printf("*%d,%d,%d*\\n",
            (int)(&generations[0]) ==
            (int)(&generations[0].head.gc.gc_next),
            (int)(&generations[0]) ==
            (int)(&generations[0].head.gc.gc_prev),
            (int)(&generations[0]) ==
            (int)(&generations[1])
          );
          int x1 = (int)(&generations[0]);
          int x2 = (int)(&generations[1]);
          printf("*%d*\\n", x1 == x2);
          for (int i = 0; i < NUM_GENERATIONS; i++) {
            PyGC_Head *list = GEN_HEAD(i);
            printf("%d:%d,%d\\n", i, (int)list == (int)(list->gc.gc_prev), (int)list ==(int)(list->gc.gc_next));
          }
          printf("*%d,%d,%d*\\n", sizeof(PyGC_Head), sizeof(gc_generation), int(GEN_HEAD(2)) - int(GEN_HEAD(1)));
        }
      '''
      if Settings.QUANTUM_SIZE == 1:
        # Compressed memory. Note that sizeof() does give the fat sizes, however!
        self.do_run(src, '*0,0,0,1,2,3,4,5*\n*1,0,0*\n*0*\n0:1,1\n1:1,1\n2:1,1\n*12,20,5*')
      else:
        if self.is_le32():
          self.do_run(src, '*0,0,0,4,8,16,20,24*\n*1,0,0*\n*0*\n0:1,1\n1:1,1\n2:1,1\n*16,24,24*')
        else:
          self.do_run(src, '*0,0,0,4,8,12,16,20*\n*1,0,0*\n*0*\n0:1,1\n1:1,1\n2:1,1\n*12,20,20*')

  def test_ptrtoint(self):
      if self.emcc_args is None: return self.skip('requires emcc')

      runner = self
      def check_warnings(output):
          runner.assertEquals(filter(lambda line: 'Warning' in line, output.split('\n')).__len__(), 4)

      test_path = path_from_root('tests', 'core', 'test_ptrtoint')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output, output_processor=check_warnings)

  def test_sizeof(self):
      if self.emcc_args is None: return self.skip('requires emcc')
      # Has invalid writes between printouts
      Settings.SAFE_HEAP = 0

      test_path = path_from_root('tests', 'core', 'test_sizeof')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output, [], lambda x, err: x.replace('\n', '*'))

  def test_float_h(self):
    process = Popen([PYTHON, EMCC, path_from_root('tests', 'float+.c')], stdout=PIPE, stderr=PIPE)
    process.communicate()
    assert process.returncode is 0, 'float.h should agree with our system'

  def test_llvm_used(self):
    Building.LLVM_OPTS = 3

    test_path = path_from_root('tests', 'core', 'test_llvm_used')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_emscripten_api(self):
      #if Settings.MICRO_OPTS or Settings.RELOOP or Building.LLVM_OPTS: return self.skip('FIXME')

      test_path = path_from_root('tests', 'core', 'test_emscripten_api')
      src, output = (test_path + s for s in ('.in', '.out'))

      check = '''
def process(filename):
  src = open(filename, 'r').read()
  # TODO: restore this (see comment in emscripten.h) assert '// hello from the source' in src
'''
      Settings.EXPORTED_FUNCTIONS = ['_main', '_save_me_aimee']
      self.do_run_from_file(src, output, post_build=check)

      # test EXPORT_ALL
      Settings.EXPORTED_FUNCTIONS = []
      Settings.EXPORT_ALL = 1
      self.do_run_from_file(src, output, post_build=check)

  def test_emscripten_get_now(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('requires ta2')

      if self.run_name == 'o2':
        self.emcc_args += ['--closure', '1'] # Use closure here for some additional coverage
      self.do_run(open(path_from_root('tests', 'emscripten_get_now.cpp')).read(), 'Timer resolution is good.')

  def test_inlinejs(self):
      if not self.is_le32(): return self.skip('le32 needed for inline js')

      test_path = path_from_root('tests', 'core', 'test_inlinejs')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

      if self.emcc_args == []: # opts will eliminate the comments
        out = open('src.cpp.o.js').read()
        for i in range(1, 5): assert ('comment%d' % i) in out

  def test_inlinejs2(self):
      if not self.is_le32(): return self.skip('le32 needed for inline js')

      test_path = path_from_root('tests', 'core', 'test_inlinejs2')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_inlinejs3(self):
      test_path = path_from_root('tests', 'core', 'test_inlinejs3')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_memorygrowth(self):
    if Settings.USE_TYPED_ARRAYS == 0: return self.skip('memory growth is only supported with typed arrays')
    if Settings.ASM_JS: return self.skip('asm does not support memory growth yet')

    # With typed arrays in particular, it is dangerous to use more memory than TOTAL_MEMORY,
    # since we then need to enlarge the heap(s).
    src = r'''
      #include <stdio.h>
      #include <stdlib.h>
      #include <string.h>
      #include <assert.h>
      #include "emscripten.h"

      int main(int argc, char **argv)
      {
        char *buf1 = (char*)malloc(100);
        char *data1 = "hello";
        memcpy(buf1, data1, strlen(data1)+1);

        float *buf2 = (float*)malloc(100);
        float pie = 4.955;
        memcpy(buf2, &pie, sizeof(float));

        printf("*pre: %s,%.3f*\n", buf1, buf2[0]);

        int totalMemory = emscripten_run_script_int("TOTAL_MEMORY");
        char *buf3 = (char*)malloc(totalMemory+1);
        buf3[argc] = (int)buf2;
        if (argc % 7 == 6) printf("%d\n", memcpy(buf3, buf1, argc));
        char *buf4 = (char*)malloc(100);
        float *buf5 = (float*)malloc(100);
        //printf("totalMemory: %d bufs: %d,%d,%d,%d,%d\n", totalMemory, buf1, buf2, buf3, buf4, buf5);
        assert((int)buf4 > (int)totalMemory && (int)buf5 > (int)totalMemory);

        printf("*%s,%.3f*\n", buf1, buf2[0]); // the old heap data should still be there

        memcpy(buf4, buf1, strlen(data1)+1);
        memcpy(buf5, buf2, sizeof(float));
        printf("*%s,%.3f*\n", buf4, buf5[0]); // and the new heap space should work too

        return 0;
      }
    '''

    # Fail without memory growth
    self.do_run(src, 'Cannot enlarge memory arrays.')
    fail = open('src.cpp.o.js').read()

    # Win with it
    Settings.ALLOW_MEMORY_GROWTH = 1
    self.do_run(src, '*pre: hello,4.955*\n*hello,4.955*\n*hello,4.955*')
    win = open('src.cpp.o.js').read()

    if self.emcc_args and '-O2' in self.emcc_args:
      # Make sure ALLOW_MEMORY_GROWTH generates different code (should be less optimized)
      code_start = 'var TOTAL_MEMORY = '
      fail = fail[fail.find(code_start):]
      win = win[win.find(code_start):]
      assert len(fail) < len(win), 'failing code - without memory growth on - is more optimized, and smaller'

  def test_ssr(self): # struct self-ref
      src = '''
        #include <stdio.h>

        // see related things in openjpeg
        typedef struct opj_mqc_state {
          unsigned int qeval;
          int mps;
          struct opj_mqc_state *nmps;
          struct opj_mqc_state *nlps;
        } opj_mqc_state_t;

        static opj_mqc_state_t mqc_states[2] = {
          {0x5600, 0, &mqc_states[2], &mqc_states[3]},
          {0x5602, 1, &mqc_states[3], &mqc_states[2]},
        };

        int main() {
          printf("*%d*\\n", (int)(mqc_states+1)-(int)mqc_states);
          for (int i = 0; i < 2; i++)
            printf("%d:%d,%d,%d,%d\\n", i, mqc_states[i].qeval, mqc_states[i].mps,
                   (int)mqc_states[i].nmps-(int)mqc_states, (int)mqc_states[i].nlps-(int)mqc_states);
          return 0;
        }
        '''
      if Settings.QUANTUM_SIZE == 1:
        self.do_run(src, '''*4*\n0:22016,0,8,12\n1:22018,1,12,8\n''')
      else:
        self.do_run(src, '''*16*\n0:22016,0,32,48\n1:22018,1,48,32\n''')

  def test_tinyfuncstr(self):
      if self.emcc_args is None: return self.skip('requires emcc')

      test_path = path_from_root('tests', 'core', 'test_tinyfuncstr')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_llvmswitch(self):
      Settings.CORRECT_SIGNS = 1

      test_path = path_from_root('tests', 'core', 'test_llvmswitch')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  # By default, when user has not specified a -std flag, Emscripten should always build .cpp files using the C++03 standard,
  # i.e. as if "-std=c++03" had been passed on the command line. On Linux with Clang 3.2 this is the case, but on Windows
  # with Clang 3.2 -std=c++11 has been chosen as default, because of
  # < jrose> clb: it's deliberate, with the idea that for people who don't care about the standard, they should be using the "best" thing we can offer on that platform
  def test_cxx03_do_run(self):
    test_path = path_from_root('tests', 'core', 'test_cxx03_do_run')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_bigswitch(self):
    if self.run_name != 'default': return self.skip('TODO: issue #781')

    src = open(path_from_root('tests', 'bigswitch.cpp')).read()
    self.do_run(src, '''34962: GL_ARRAY_BUFFER (0x8892)
26214: what?
35040: GL_STREAM_DRAW (0x88E0)
''', args=['34962', '26214', '35040'])

  def test_indirectbr(self):
      Building.COMPILER_TEST_OPTS = filter(lambda x: x != '-g', Building.COMPILER_TEST_OPTS)

      test_path = path_from_root('tests', 'core', 'test_indirectbr')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_indirectbr_many(self):
      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('blockaddr > 255 requires ta2')

      test_path = path_from_root('tests', 'core', 'test_indirectbr_many')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_pack(self):
      src = '''
        #include <stdio.h>
        #include <string.h>

        #pragma pack(push,1)
        typedef struct header
        {
            unsigned char  id;
            unsigned short colour;
            unsigned char  desc;
        } header;
        #pragma pack(pop)

        typedef struct fatheader
        {
            unsigned char  id;
            unsigned short colour;
            unsigned char  desc;
        } fatheader;

        int main( int argc, const char *argv[] ) {
          header h, *ph = 0;
          fatheader fh, *pfh = 0;
          printf("*%d,%d,%d*\\n", sizeof(header), (int)((int)&h.desc - (int)&h.id), (int)(&ph[1])-(int)(&ph[0]));
          printf("*%d,%d,%d*\\n", sizeof(fatheader), (int)((int)&fh.desc - (int)&fh.id), (int)(&pfh[1])-(int)(&pfh[0]));
          return 0;
        }
        '''
      if Settings.QUANTUM_SIZE == 1:
        self.do_run(src, '*4,2,3*\n*6,2,3*')
      else:
        self.do_run(src, '*4,3,4*\n*6,4,6*')

  def test_varargs(self):
      if Settings.QUANTUM_SIZE == 1: return self.skip('FIXME: Add support for this')
      if not self.is_le32(): return self.skip('we do not support all varargs stuff without le32')

      test_path = path_from_root('tests', 'core', 'test_varargs')
      src, output = (test_path + s for s in ('.in', '.out'))

      self.do_run_from_file(src, output)

  def test_varargs_byval(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('FIXME: Add support for this')
    if self.is_le32(): return self.skip('clang cannot compile this code with that target yet')

    src = r'''
      #include <stdio.h>
      #include <stdarg.h>

      typedef struct type_a {
        union {
          double f;
          void *p;
          int i;
          short sym;
        } value;
      } type_a;

      enum mrb_vtype {
        MRB_TT_FALSE = 0,   /*   0 */
        MRB_TT_CLASS = 9    /*   9 */
      };

      typedef struct type_b {
        enum mrb_vtype tt:8;
      } type_b;

      void print_type_a(int argc, ...);
      void print_type_b(int argc, ...);

      int main(int argc, char *argv[])
      {
        type_a a;
        type_b b;
        a.value.p = (void*) 0x12345678;
        b.tt = MRB_TT_CLASS;

        printf("The original address of a is: %p\n", a.value.p);
        printf("The original type of b is: %d\n", b.tt);

        print_type_a(1, a);
        print_type_b(1, b);

        return 0;
      }

      void print_type_a(int argc, ...) {
        va_list ap;
        type_a a;

        va_start(ap, argc);
        a = va_arg(ap, type_a);
        va_end(ap);

        printf("The current address of a is: %p\n", a.value.p);
      }

      void print_type_b(int argc, ...) {
        va_list ap;
        type_b b;

        va_start(ap, argc);
        b = va_arg(ap, type_b);
        va_end(ap);

        printf("The current type of b is: %d\n", b.tt);
      }
      '''
    self.do_run(src, '''The original address of a is: 0x12345678
The original type of b is: 9
The current address of a is: 0x12345678
The current type of b is: 9
''')

  def test_functionpointer_libfunc_varargs(self):
    test_path = path_from_root('tests', 'core', 'test_functionpointer_libfunc_varargs')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_structbyval(self):
      Settings.INLINING_LIMIT = 50

      # part 1: make sure that normally, passing structs by value works

      src = r'''
        #include <stdio.h>

        struct point
        {
          int x, y;
        };

        void dump(struct point p) {
          p.x++; // should not modify
          p.y++; // anything in the caller!
          printf("dump: %d,%d\n", p.x, p.y);
        }

        void dumpmod(struct point *p) {
          p->x++; // should not modify
          p->y++; // anything in the caller!
          printf("dump: %d,%d\n", p->x, p->y);
        }

        int main( int argc, const char *argv[] ) {
          point p = { 54, 2 };
          printf("pre:  %d,%d\n", p.x, p.y);
          dump(p);
          void (*dp)(point p) = dump; // And, as a function pointer
          dp(p);
          printf("post: %d,%d\n", p.x, p.y);
          dumpmod(&p);
          dumpmod(&p);
          printf("last: %d,%d\n", p.x, p.y);
          return 0;
        }
      '''
      self.do_run(src, 'pre:  54,2\ndump: 55,3\ndump: 55,3\npost: 54,2\ndump: 55,3\ndump: 56,4\nlast: 56,4')

      # Check for lack of warning in the generated code (they should appear in part 2)
      generated = open(os.path.join(self.get_dir(), 'src.cpp.o.js')).read()
      assert 'Casting a function pointer type to another with a different number of arguments.' not in generated, 'Unexpected warning'

      # part 2: make sure we warn about mixing c and c++ calling conventions here

      if not (self.emcc_args is None or self.emcc_args == []): return # Optimized code is missing the warning comments

      header = r'''
        struct point
        {
          int x, y;
        };

      '''
      open(os.path.join(self.get_dir(), 'header.h'), 'w').write(header)

      supp = r'''
        #include <stdio.h>
        #include "header.h"

        void dump(struct point p) {
          p.x++; // should not modify
          p.y++; // anything in the caller!
          printf("dump: %d,%d\n", p.x, p.y);
        }
      '''
      supp_name = os.path.join(self.get_dir(), 'supp.c')
      open(supp_name, 'w').write(supp)

      main = r'''
        #include <stdio.h>
        #include "header.h"

        #ifdef __cplusplus
        extern "C" {
        #endif
          void dump(struct point p);
        #ifdef __cplusplus
        }
        #endif

        int main( int argc, const char *argv[] ) {
          struct point p = { 54, 2 };
          printf("pre:  %d,%d\n", p.x, p.y);
          dump(p);
          void (*dp)(struct point p) = dump; // And, as a function pointer
          dp(p);
          printf("post: %d,%d\n", p.x, p.y);
          return 0;
        }
      '''
      main_name = os.path.join(self.get_dir(), 'main.cpp')
      open(main_name, 'w').write(main)

      Building.emcc(supp_name)
      Building.emcc(main_name)
      all_name = os.path.join(self.get_dir(), 'all.bc')
      Building.link([supp_name + '.o', main_name + '.o'], all_name)

      # This will fail! See explanation near the warning we check for, in the compiler source code
      output = Popen([PYTHON, EMCC, all_name], stderr=PIPE).communicate()

      # Check for warning in the generated code
      generated = open(os.path.join(self.get_dir(), 'src.cpp.o.js')).read()
      if 'i386-pc-linux-gnu' in COMPILER_OPTS:
        assert 'Casting a function pointer type to a potentially incompatible one' in output[1], 'Missing expected warning'
      else:
        print >> sys.stderr, 'skipping C/C++ conventions warning check, since not i386-pc-linux-gnu'

  def test_stdlibs(self):
      if self.emcc_args is None: return self.skip('requires emcc')
      if Settings.USE_TYPED_ARRAYS == 2:
          # Typed arrays = 2 + safe heap prints a warning that messes up our output.
          Settings.SAFE_HEAP = 0
      src = '''
        #include <stdio.h>
        #include <stdlib.h>
        #include <sys/time.h>

        void clean()
        {
          printf("*cleaned*\\n");
        }

        int comparer(const void *a, const void *b) {
          int aa = *((int*)a);
          int bb = *((int*)b);
          return aa - bb;
        }

        int main() {
          // timeofday
          timeval t;
          gettimeofday(&t, NULL);
          printf("*%d,%d\\n", int(t.tv_sec), int(t.tv_usec)); // should not crash

          // atexit
          atexit(clean);

          // qsort
          int values[6] = { 3, 2, 5, 1, 5, 6 };
          qsort(values, 5, sizeof(int), comparer);
          printf("*%d,%d,%d,%d,%d,%d*\\n", values[0], values[1], values[2], values[3], values[4], values[5]);

          printf("*stdin==0:%d*\\n", stdin == 0); // check that external values are at least not NULL
          printf("*%%*\\n");
          printf("*%.1ld*\\n", 5);

          printf("*%.1f*\\n", strtod("66", NULL)); // checks dependency system, as our strtod needs _isspace etc.

          printf("*%ld*\\n", strtol("10", NULL, 0));
          printf("*%ld*\\n", strtol("0", NULL, 0));
          printf("*%ld*\\n", strtol("-10", NULL, 0));
          printf("*%ld*\\n", strtol("12", NULL, 16));

          printf("*%lu*\\n", strtoul("10", NULL, 0));
          printf("*%lu*\\n", strtoul("0", NULL, 0));
          printf("*%lu*\\n", strtoul("-10", NULL, 0));

          printf("*malloc(0)!=0:%d*\\n", malloc(0) != 0); // We should not fail horribly

          return 0;
        }
        '''

      self.do_run(src, '*1,2,3,5,5,6*\n*stdin==0:0*\n*%*\n*5*\n*66.0*\n*10*\n*0*\n*-10*\n*18*\n*10*\n*0*\n*4294967286*\n*malloc(0)!=0:1*\n*cleaned*')

      src = r'''
        #include <stdio.h>
        #include <stdbool.h>

        int main() {
          bool x = true;
          bool y = false;
          printf("*%d*\n", x != y);
          return 0;
        }
      '''

      self.do_run(src, '*1*', force_c=True)

  def test_strtoll_hex(self):
    if self.emcc_args is None: return self.skip('requires emcc')

    # tests strtoll for hex strings (0x...) 
    test_path = path_from_root('tests', 'core', 'test_strtoll_hex')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strtoll_dec(self):
    if self.emcc_args is None: return self.skip('requires emcc')

    # tests strtoll for decimal strings (0x...) 
    test_path = path_from_root('tests', 'core', 'test_strtoll_dec')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strtoll_bin(self):
    if self.emcc_args is None: return self.skip('requires emcc')

    # tests strtoll for binary strings (0x...) 
    test_path = path_from_root('tests', 'core', 'test_strtoll_bin')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strtoll_oct(self):
    if self.emcc_args is None: return self.skip('requires emcc')

    # tests strtoll for decimal strings (0x...) 
    test_path = path_from_root('tests', 'core', 'test_strtoll_oct')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strtol_hex(self):
    # tests strtoll for hex strings (0x...) 
    test_path = path_from_root('tests', 'core', 'test_strtol_hex')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strtol_dec(self):
    # tests strtoll for decimal strings (0x...) 
    test_path = path_from_root('tests', 'core', 'test_strtol_dec')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strtol_bin(self):
    # tests strtoll for binary strings (0x...) 
    test_path = path_from_root('tests', 'core', 'test_strtol_bin')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_strtol_oct(self):
    # tests strtoll for decimal strings (0x...) 
    test_path = path_from_root('tests', 'core', 'test_strtol_oct')
    src, output = (test_path + s for s in ('.in', '.out'))

    self.do_run_from_file(src, output)

  def test_atexit(self):
    # Confirms they are called in reverse order
    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      static void cleanA() {
        printf("A");
      }
      static void cleanB() {
        printf("B");
      }

      int main() {
        atexit(cleanA);
        atexit(cleanB);
        return 0;
      }
      '''
    self.do_run(src, 'BA')

  def test_pthread_specific(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    src = open(path_from_root('tests', 'pthread', 'specific.c'), 'r').read()
    expected = open(path_from_root('tests', 'pthread', 'specific.c.txt'), 'r').read()
    self.do_run(src, expected, force_c=True)

  def test_tcgetattr(self):
    src = open(path_from_root('tests', 'termios', 'test_tcgetattr.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_time(self):
    # XXX Not sure what the right output is here. Looks like the test started failing with daylight savings changes. Modified it to pass again.
    src = open(path_from_root('tests', 'time', 'src.c'), 'r').read()
    expected = open(path_from_root('tests', 'time', 'output.txt'), 'r').read()
    expected2 = open(path_from_root('tests', 'time', 'output2.txt'), 'r').read()
    self.do_run(src, [expected, expected2],
                 extra_emscripten_args=['-H', 'libc/time.h'])
                 #extra_emscripten_args=['-H', 'libc/fcntl.h,libc/sys/unistd.h,poll.h,libc/math.h,libc/langinfo.h,libc/time.h'])

  def test_timeb(self):
    # Confirms they are called in reverse order
    src = r'''
      #include <stdio.h>
      #include <assert.h>
      #include <sys/timeb.h>

      int main() {
        timeb tb;
        tb.timezone = 1;
        printf("*%d\n", ftime(&tb));
        assert(tb.time > 10000);
        assert(tb.timezone == 0);
        assert(tb.dstflag == 0);
        return 0;
      }
      '''
    self.do_run(src, '*0\n')

  def test_time_c(self):
    src = r'''
      #include <time.h>
      #include <stdio.h>

      int main() {
        time_t t = time(0);
        printf("time: %s\n", ctime(&t));
      }
    '''
    self.do_run(src, 'time: ') # compilation check, mainly

  def test_gmtime(self):
    src = r'''
      #include <stdio.h>
      #include <stdlib.h>
      #include <time.h>
      #include <assert.h>

      int main(void)
      {
          time_t t=time(NULL);
          struct tm *ptm=gmtime(&t);
          struct tm tmCurrent=*ptm;
          int hour=tmCurrent.tm_hour;

          t-=hour*3600; // back to midnight
          int yday = -1;
          for(hour=0;hour<24;hour++)
          {
              ptm=gmtime(&t);
              // tm_yday must be constant all day...
              printf("yday: %d, hour: %d\n", ptm->tm_yday, hour);
              if (yday == -1) yday = ptm->tm_yday;
              else assert(yday == ptm->tm_yday);
              t+=3600; // add one hour
          }
          printf("ok!\n");
          return(0);
      }
    '''
    self.do_run(src, '''ok!''')

  def test_strptime_tm(self):
    src=r'''
      #include <time.h>
      #include <stdio.h>
      #include <string.h>

      int main() {
        struct tm tm;
        char *ptr = strptime("17410105012000", "%H%M%S%d%m%Y", &tm);

        printf("%s: %s, %d/%d/%d %d:%d:%d", 
          (ptr != NULL && *ptr=='\0') ? "OK" : "ERR", 
          tm.tm_wday == 0 ? "Sun" : (tm.tm_wday == 1 ? "Mon" : (tm.tm_wday == 2 ? "Tue" : (tm.tm_wday == 3 ? "Wed" : (tm.tm_wday == 4 ? "Thu" : (tm.tm_wday == 5 ? "Fri" : (tm.tm_wday == 6 ? "Sat" : "ERR")))))),
          tm.tm_mon+1,
          tm.tm_mday,
          tm.tm_year+1900,
          tm.tm_hour,
          tm.tm_min,
          tm.tm_sec            
        );
      }
    ''' 
    self.do_run(src, 'OK: Wed, 1/5/2000 17:41:1')

  def test_strptime_days(self):
    src = r'''
      #include <time.h>
      #include <stdio.h>
      #include <string.h>

      static const struct {
        const char *input;
        const char *format;
      } day_tests[] = {
        { "2000-01-01", "%Y-%m-%d"},
        { "03/03/00", "%D"},
        { "9/9/99", "%x"},
        { "19990502123412", "%Y%m%d%H%M%S"},
        { "2001 20 Mon", "%Y %U %a"},
        { "2006 4 Fri", "%Y %U %a"},
        { "2001 21 Mon", "%Y %W %a"},
        { "2013 29 Wed", "%Y %W %a"},
        { "2000-01-01 08:12:21 AM", "%Y-%m-%d %I:%M:%S %p"},
        { "2000-01-01 08:12:21 PM", "%Y-%m-%d %I:%M:%S %p"},
        { "2001 17 Tue", "%Y %U %a"},
        { "2001 8 Thursday", "%Y %W %a"},
      };

      int main() {  
        struct tm tm;

        for (int i = 0; i < sizeof (day_tests) / sizeof (day_tests[0]); ++i) {
          memset (&tm, '\0', sizeof (tm));
          char *ptr = strptime(day_tests[i].input, day_tests[i].format, &tm);

          printf("%s: %d/%d/%d (%dth DoW, %dth DoY)\n", (ptr != NULL && *ptr=='\0') ? "OK" : "ERR", tm.tm_mon+1, tm.tm_mday, 1900+tm.tm_year, tm.tm_wday, tm.tm_yday);
        }
      }
    '''
    self.do_run(src, 'OK: 1/1/2000 (6th DoW, 0th DoY)\n'\
                     'OK: 3/3/2000 (5th DoW, 62th DoY)\n'\
                     'OK: 9/9/1999 (4th DoW, 251th DoY)\n'\
                     'OK: 5/2/1999 (0th DoW, 121th DoY)\n'\
                     'OK: 5/21/2001 (1th DoW, 140th DoY)\n'\
                     'OK: 1/27/2006 (5th DoW, 26th DoY)\n'\
                     'OK: 5/21/2001 (1th DoW, 140th DoY)\n'\
                     'OK: 7/24/2013 (3th DoW, 204th DoY)\n'\
                     'OK: 1/1/2000 (6th DoW, 0th DoY)\n'\
                     'OK: 1/1/2000 (6th DoW, 0th DoY)\n'\
                     'OK: 5/1/2001 (2th DoW, 120th DoY)\n'\
                     'OK: 2/22/2001 (4th DoW, 52th DoY)\n'\
    )

  def test_strptime_reentrant(self):
    src=r'''
      #include <time.h>
      #include <stdio.h>
      #include <string.h>
      #include <stdlib.h>

      int main () {
        int result = 0;
        struct tm tm;

        memset (&tm, 0xaa, sizeof (tm));

        /* Test we don't crash on uninitialized struct tm.
           Some fields might contain bogus values until everything
           needed is initialized, but we shouldn't crash.  */
        if (strptime ("2007", "%Y", &tm) == NULL
            || strptime ("12", "%d", &tm) == NULL
            || strptime ("Feb", "%b", &tm) == NULL
            || strptime ("13", "%M", &tm) == NULL
            || strptime ("21", "%S", &tm) == NULL
            || strptime ("16", "%H", &tm) == NULL) {
          printf("ERR: returned NULL");
          exit(EXIT_FAILURE);
        }

        if (tm.tm_sec != 21 || tm.tm_min != 13 || tm.tm_hour != 16
            || tm.tm_mday != 12 || tm.tm_mon != 1 || tm.tm_year != 107
            || tm.tm_wday != 1 || tm.tm_yday != 42) {
          printf("ERR: unexpected tm content (1) - %d/%d/%d %d:%d:%d", tm.tm_mon+1, tm.tm_mday, tm.tm_year+1900, tm.tm_hour, tm.tm_min, tm.tm_sec);
          exit(EXIT_FAILURE);
        }

        if (strptime ("8", "%d", &tm) == NULL) {
          printf("ERR: strptime failed");
          exit(EXIT_FAILURE);
        }

        if (tm.tm_sec != 21 || tm.tm_min != 13 || tm.tm_hour != 16
            || tm.tm_mday != 8 || tm.tm_mon != 1 || tm.tm_year != 107
            || tm.tm_wday != 4 || tm.tm_yday != 38) {
          printf("ERR: unexpected tm content (2) - %d/%d/%d %d:%d:%d", tm.tm_mon+1, tm.tm_mday, tm.tm_year+1900, tm.tm_hour, tm.tm_min, tm.tm_sec);
          exit(EXIT_FAILURE);
        }

        printf("OK");
      }
    '''
    self.do_run(src, 'OK')

  def test_strftime(self):
    src=r'''
      #include <time.h>
      #include <stdio.h>
      #include <string.h>
      #include <stdlib.h>

      void test(int result, const char* comment, const char* parsed = "") {
        printf("%d",result);
        if (!result) {
          printf("\nERROR: %s (\"%s\")\n", comment, parsed);
        }
      }

      int cmp(const char *s1, const char *s2) {
        for ( ; *s1 == *s2 ; s1++,s2++ ) {
          if ( *s1 == '\0' )
            break;
        } 

        return (*s1 - *s2);
      }

      int main() {
          struct tm tm;
          char s[1000];
          size_t size;
          
          tm.tm_sec = 4;
          tm.tm_min = 23;
          tm.tm_hour = 20;
          tm.tm_mday = 21;
          tm.tm_mon = 1;
          tm.tm_year = 74;
          tm.tm_wday = 4;
          tm.tm_yday = 51;
          tm.tm_isdst = 0;
          
          size = strftime(s, 1000, "", &tm);
          test((size==0) && (*s=='\0'), "strftime test #1", s);

          size = strftime(s, 1000, "%a", &tm);
          test((size==3) && !cmp(s, "Thu"), "strftime test #2", s);

          size = strftime(s, 1000, "%A", &tm);
          test((size==8) && !cmp(s, "Thursday"), "strftime test #3", s);

          size = strftime(s, 1000, "%b", &tm);
          test((size==3) && !cmp(s, "Feb"), "strftime test #4", s);

          size = strftime(s, 1000, "%B", &tm);
          test((size==8) && !cmp(s, "February"),
                             "strftime test #5", s);

          size = strftime(s, 1000, "%d", &tm);
          test((size==2) && !cmp(s, "21"),
                             "strftime test #6", s);

          size = strftime(s, 1000, "%H", &tm);
          test((size==2) && !cmp(s, "20"),
                             "strftime test #7", s);

          size = strftime(s, 1000, "%I", &tm);
          test((size==2) && !cmp(s, "08"),
                             "strftime test #8", s);

          size = strftime(s, 1000, "%j", &tm);
          test((size==3) && !cmp(s, "052"),
                             "strftime test #9", s);

          size = strftime(s, 1000, "%m", &tm);
          test((size==2) && !cmp(s, "02"),
                             "strftime test #10", s);

          size = strftime(s, 1000, "%M", &tm);
          test((size==2) && !cmp(s, "23"),
                             "strftime test #11", s);

          size = strftime(s, 1000, "%p", &tm);
          test((size==2) && !cmp(s, "PM"),
                             "strftime test #12", s);

          size = strftime(s, 1000, "%S", &tm);
          test((size==2) && !cmp(s, "04"),
                             "strftime test #13", s);

          size = strftime(s, 1000, "%U", &tm);
          test((size==2) && !cmp(s, "07"),
                             "strftime test #14", s);

          size = strftime(s, 1000, "%w", &tm);
          test((size==1) && !cmp(s, "4"),
                             "strftime test #15", s);

          size = strftime(s, 1000, "%W", &tm);
          test((size==2) && !cmp(s, "07"),
                             "strftime test #16", s);

          size = strftime(s, 1000, "%y", &tm);
          test((size==2) && !cmp(s, "74"),
                             "strftime test #17", s);

          size = strftime(s, 1000, "%Y", &tm);
          test((size==4) && !cmp(s, "1974"),
                             "strftime test #18", s);

          size = strftime(s, 1000, "%%", &tm);
          test((size==1) && !cmp(s, "%"),
                             "strftime test #19", s);

          size = strftime(s, 5, "%Y", &tm);
          test((size==4) && !cmp(s, "1974"),
                             "strftime test #20", s);

          size = strftime(s, 4, "%Y", &tm);
          test((size==0), "strftime test #21", s);

          tm.tm_mon = 0;
          tm.tm_mday = 1;
          size = strftime(s, 10, "%U", &tm);
          test((size==2) && !cmp(s, "00"), "strftime test #22", s);

          size = strftime(s, 10, "%W", &tm);
          test((size==2) && !cmp(s, "00"), "strftime test #23", s);

          // 1/1/1973 was a Sunday and is in CW 1
          tm.tm_year = 73;
          size = strftime(s, 10, "%W", &tm);
          test((size==2) && !cmp(s, "01"), "strftime test #24", s);

          // 1/1/1978 was a Monday and is in CW 1
          tm.tm_year = 78;
          size = strftime(s, 10, "%U", &tm);
          test((size==2) && !cmp(s, "01"), "strftime test #25", s);

          // 2/1/1999
          tm.tm_year = 99;
          tm.tm_yday = 1;
          size = strftime(s, 10, "%G (%V)", &tm);
          test((size==9) && !cmp(s, "1998 (53)"), "strftime test #26", s);

          size = strftime(s, 10, "%g", &tm);
          test((size==2) && !cmp(s, "98"), "strftime test #27", s);

          // 30/12/1997
          tm.tm_year = 97;
          tm.tm_yday = 363;
          size = strftime(s, 10, "%G (%V)", &tm);
          test((size==9) && !cmp(s, "1998 (01)"), "strftime test #28", s);

          size = strftime(s, 10, "%g", &tm);
          test((size==2) && !cmp(s, "98"), "strftime test #29", s);
      } 
    '''
    self.do_run(src, '11111111111111111111111111111')

  def test_intentional_fault(self):
    # Some programs intentionally segfault themselves, we should compile that into a throw
    src = r'''
      int main () {
        *(volatile char *)0 = 0;
        return *(volatile char *)0;
      }
      '''
    self.do_run(src, 'fault on write to 0' if not Settings.ASM_JS else 'abort()')

  def test_trickystring(self):
    src = r'''
      #include <stdio.h>

      typedef struct
      {
        int (*f)(void *);
        void *d;
        char s[16];
      } LMEXFunctionStruct;

      int f(void *user)
      {
        return 0;
      }

      static LMEXFunctionStruct const a[] =
      {
        {f, (void *)(int)'a', "aa"}
      };

      int main()
      {
        printf("ok\n");
        return a[0].f(a[0].d);
      }
    '''
    self.do_run(src, 'ok\n')

  def test_statics(self):
      # static initializers save i16 but load i8 for some reason (or i64 and load i8)
      if Settings.SAFE_HEAP:
        Settings.SAFE_HEAP = 3
        Settings.SAFE_HEAP_LINES = ['src.cpp:19', 'src.cpp:26', 'src.cpp:28']

      src = '''
        #include <stdio.h>
        #include <string.h>

        #define CONSTRLEN 32

        char * (*func)(char *, const char *) = NULL;

        void conoutfv(const char *fmt)
        {
            static char buf[CONSTRLEN];
            func(buf, fmt); // call by function pointer to make sure we test strcpy here
            puts(buf);
        }

        struct XYZ {
          float x, y, z;
          XYZ(float a, float b, float c) : x(a), y(b), z(c) { }
          static const XYZ& getIdentity()
          {
            static XYZ iT(1,2,3);
            return iT;
          }
        };
        struct S {
          static const XYZ& getIdentity()
          {
            static const XYZ iT(XYZ::getIdentity());
            return iT;
          }
        };

        int main() {
          func = &strcpy;
          conoutfv("*staticccz*");
          printf("*%.2f,%.2f,%.2f*\\n", S::getIdentity().x, S::getIdentity().y, S::getIdentity().z);
          return 0;
        }
        '''
      self.do_run(src, '*staticccz*\n*1.00,2.00,3.00*')

  def test_copyop(self):
      if self.emcc_args is None: return self.skip('requires emcc')

      # clang generated code is vulnerable to this, as it uses
      # memcpy for assignments, with hardcoded numbers of bytes
      # (llvm-gcc copies items one by one). See QUANTUM_SIZE in
      # settings.js.
      src = '''
        #include <stdio.h>
        #include <math.h>
        #include <string.h>

        struct vec {
          double x,y,z;
          vec() : x(0), y(0), z(0) { };
          vec(const double a, const double b, const double c) : x(a), y(b), z(c) { };
        };

        struct basis {
          vec a, b, c;
          basis(const vec& v) {
            a=v; // should not touch b!
            printf("*%.2f,%.2f,%.2f*\\n", b.x, b.y, b.z);
          }
        };

        int main() {
          basis B(vec(1,0,0));

          // Part 2: similar problem with memset and memmove
          int x = 1, y = 77, z = 2;
          memset((void*)&x, 0, sizeof(int));
          memset((void*)&z, 0, sizeof(int));
          printf("*%d,%d,%d*\\n", x, y, z);
          memcpy((void*)&x, (void*)&z, sizeof(int));
          memcpy((void*)&z, (void*)&x, sizeof(int));
          printf("*%d,%d,%d*\\n", x, y, z);
          memmove((void*)&x, (void*)&z, sizeof(int));
          memmove((void*)&z, (void*)&x, sizeof(int));
          printf("*%d,%d,%d*\\n", x, y, z);
          return 0;
        }
        '''
      self.do_run(src, '*0.00,0.00,0.00*\n*0,77,0*\n*0,77,0*\n*0,77,0*')

  def test_memcpy_memcmp(self):
      src = '''
        #include <stdio.h>
        #include <string.h>
        #include <assert.h>

        #define MAXX 48
        void reset(unsigned char *buffer) {
          for (int i = 0; i < MAXX; i++) buffer[i] = i+1;
        }
        void dump(unsigned char *buffer) {
          for (int i = 0; i < MAXX-1; i++) printf("%2d,", buffer[i]);
          printf("%d\\n", buffer[MAXX-1]);
        }
        int main() {
          unsigned char buffer[MAXX];
          for (int i = MAXX/4; i < MAXX-MAXX/4; i++) {
            for (int j = MAXX/4; j < MAXX-MAXX/4; j++) {
              for (int k = 1; k < MAXX/4; k++) {
                if (i == j) continue;
                if (i < j && i+k > j) continue;
                if (j < i && j+k > i) continue;
                printf("[%d,%d,%d] ", i, j, k);
                reset(buffer);
                memcpy(buffer+i, buffer+j, k);
                dump(buffer);
                assert(memcmp(buffer+i, buffer+j, k) == 0);
                buffer[i + k/2]++;
                if (buffer[i + k/2] != 0) {
                  assert(memcmp(buffer+i, buffer+j, k) > 0);
                } else {
                  assert(memcmp(buffer+i, buffer+j, k) < 0);
                }
                buffer[i + k/2]--;
                buffer[j + k/2]++;
                if (buffer[j + k/2] != 0) {
                  assert(memcmp(buffer+i, buffer+j, k) < 0);
                } else {
                  assert(memcmp(buffer+i, buffer+j, k) > 0);
                }
              }
            }
          }
          return 0;
        }
        '''
      def check(result, err):
        return hashlib.sha1(result).hexdigest()
      self.do_run(src, '6c9cdfe937383b79e52ca7a2cce83a21d9f5422c',
                  output_nicerizer = check)

  def test_memcpy2(self):
    src = r'''
      #include <stdio.h>
      #include <string.h>
      #include <assert.h>
      int main() {
        char buffer[256];
        for (int i = 0; i < 10; i++) {
          for (int j = 0; j < 10; j++) {
            for (int k = 0; k < 35; k++) {
              for (int t = 0; t < 256; t++) buffer[t] = t;
              char *dest = buffer + i + 128;
              char *src = buffer+j;
              //printf("%d, %d, %d\n", i, j, k);
              assert(memcpy(dest, src, k) == dest);
              assert(memcmp(dest, src, k) == 0);
            }
          }
        }
        printf("ok.\n");
        return 1;
      }
    '''
    self.do_run(src, 'ok.');

  def test_getopt(self):
      if self.emcc_args is None: return self.skip('needs emcc for libc')

      src = '''
        #pragma clang diagnostic ignored "-Winvalid-pp-token"
        #include <unistd.h>
        #include <stdlib.h>
        #include <stdio.h>

        int
        main(int argc, char *argv[])
        {
           int flags, opt;
           int nsecs, tfnd;

           nsecs = 0;
           tfnd = 0;
           flags = 0;
           while ((opt = getopt(argc, argv, "nt:")) != -1) {
               switch (opt) {
               case 'n':
                   flags = 1;
                   break;
               case 't':
                   nsecs = atoi(optarg);
                   tfnd = 1;
                   break;
               default: /* '?' */
                   fprintf(stderr, "Usage: %s [-t nsecs] [-n] name\\n",
                           argv[0]);
                   exit(EXIT_FAILURE);
               }
           }

           printf("flags=%d; tfnd=%d; optind=%d\\n", flags, tfnd, optind);

           if (optind >= argc) {
               fprintf(stderr, "Expected argument after options\\n");
               exit(EXIT_FAILURE);
           }

           printf("name argument = %s\\n", argv[optind]);

           /* Other code omitted */

           exit(EXIT_SUCCESS);
        }
      '''
      self.do_run(src, 'flags=1; tfnd=1; optind=4\nname argument = foobar', args=['-t', '12', '-n', 'foobar'])

  def test_getopt_long(self):
      if self.emcc_args is None: return self.skip('needs emcc for libc')

      src = '''
        #pragma clang diagnostic ignored "-Winvalid-pp-token"
        #pragma clang diagnostic ignored "-Wdeprecated-writable-strings"
        #include <stdio.h>     /* for printf */
        #include <stdlib.h>    /* for exit */
        #include <getopt.h>

        int
        main(int argc, char **argv)
        {
           int c;
           int digit_optind = 0;

           while (1) {
               int this_option_optind = optind ? optind : 1;
               int option_index = 0;
               static struct option long_options[] = {
                   {"add",     required_argument, 0,  0 },
                   {"append",  no_argument,       0,  0 },
                   {"delete",  required_argument, 0,  0 },
                   {"verbose", no_argument,       0,  0 },
                   {"create",  required_argument, 0, 'c'},
                   {"file",    required_argument, 0,  0 },
                   {0,         0,                 0,  0 }
               };

               c = getopt_long(argc, argv, "abc:d:012",
                        long_options, &option_index);
               if (c == -1)
                   break;

               switch (c) {
               case 0:
                   printf("option %s", long_options[option_index].name);
                   if (optarg)
                       printf(" with arg %s", optarg);
                   printf("\\n");
                   break;

               case '0':
               case '1':
               case '2':
                   if (digit_optind != 0 && digit_optind != this_option_optind)
                     printf("digits occur in two different argv-elements.\\n");
                   digit_optind = this_option_optind;
                   printf("option %c\\n", c);
                   break;

               case 'a':
                   printf("option a\\n");
                   break;

               case 'b':
                   printf("option b\\n");
                   break;

               case 'c':
                   printf("option c with value '%s'\\n", optarg);
                   break;

               case 'd':
                   printf("option d with value '%s'\\n", optarg);
                   break;

               case '?':
                   break;

               default:
                   printf("?? getopt returned character code 0%o ??\\n", c);
               }
           }

           if (optind < argc) {
               printf("non-option ARGV-elements: ");
               while (optind < argc)
                   printf("%s ", argv[optind++]);
               printf("\\n");
           }

           exit(EXIT_SUCCESS);
        }
      '''
      self.do_run(src, 'option file with arg foobar\noption b', args=['--file', 'foobar', '-b'])

  def test_memmove(self):
    src = '''
      #include <stdio.h>
      #include <string.h>
      int main() {
        char str[] = "memmove can be very useful....!";
        memmove (str+20, str+15, 11);
        puts(str);
        return 0;
      }
    '''
    self.do_run(src, 'memmove can be very very useful')

  def test_memmove2(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('need ta2')

    src = r'''
      #include <stdio.h>
      #include <string.h>
      #include <assert.h>
      int main() {
        int sum = 0;
        char buffer[256];
        for (int i = 0; i < 10; i++) {
          for (int j = 0; j < 10; j++) {
            for (int k = 0; k < 35; k++) {
              for (int t = 0; t < 256; t++) buffer[t] = t;
              char *dest = buffer + i;
              char *src = buffer + j;
              if (dest == src) continue;
              //printf("%d, %d, %d\n", i, j, k);
              assert(memmove(dest, src, k) == dest);
              for (int t = 0; t < 256; t++) sum += buffer[t];
            }
          }
        }
        printf("final: %d.\n", sum);
        return 1;
      }
    '''
    self.do_run(src, 'final: -403200.');

  def test_memmove3(self):
    src = '''
      #include <stdio.h>
      #include <string.h>
      int main() {
        char str[] = "memmove can be vvery useful....!";
        memmove(str+15, str+16, 17);
        puts(str);
        return 0;
      }
    '''
    self.do_run(src, 'memmove can be very useful....!')

  def test_flexarray_struct(self):
    src = r'''
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

typedef struct
{
  uint16_t length;
  struct 
  {
    int32_t int32;
  } value[];
} Tuple;

int main() {
  Tuple T[10];
  Tuple *t = &T[0];

  t->length = 4;
  t->value->int32 = 100;

  printf("(%d, %d)\n", t->length, t->value->int32);
  return 0;
}
'''
    self.do_run(src, '(4, 100)')

  def test_bsearch(self):
    if Settings.QUANTUM_SIZE == 1: return self.skip('Test cannot work with q1')

    src = '''
        #include <stdlib.h>
        #include <stdio.h>

        int cmp(const void* key, const void* member) {
          return *(int *)key - *(int *)member;
        }

        void printResult(int* needle, int* haystack, unsigned int len) {
          void *result = bsearch(needle, haystack, len, sizeof(unsigned int), cmp);

          if (result == NULL) {
            printf("null\\n");
          } else {
            printf("%d\\n", *(unsigned int *)result);
          }
        }

        int main() {
          int a[] = { -2, -1, 0, 6, 7, 9 };
          int b[] = { 0, 1 };

          /* Find all keys that exist. */
          for(int i = 0; i < 6; i++) {
            int val = a[i];

            printResult(&val, a, 6);
          }

          /* Keys that are covered by the range of the array but aren't in
           * the array cannot be found.
           */
          int v1 = 3;
          int v2 = 8;
          printResult(&v1, a, 6);
          printResult(&v2, a, 6);

          /* Keys outside the range of the array cannot be found. */
          int v3 = -1;
          int v4 = 2;

          printResult(&v3, b, 2);
          printResult(&v4, b, 2);

          return 0;
        }
        '''

    self.do_run(src, '-2\n-1\n0\n6\n7\n9\nnull\nnull\nnull\nnull')

  def test_nestedstructs(self):
      src = '''
        #include <stdio.h>
        #include "emscripten.h"

        struct base {
          int x;
          float y;
          union {
            int a;
            float b;
          };
          char c;
        };

        struct hashtableentry {
          int key;
          base data;
        };

        struct hashset {
          typedef hashtableentry entry;
          struct chain { entry elem; chain *next; };
        //  struct chainchunk { chain chains[100]; chainchunk *next; };
        };

        struct hashtable : hashset {
          hashtable() {
            base *b = NULL;
            entry *e = NULL;
            chain *c = NULL;
            printf("*%d,%d,%d,%d,%d,%d|%d,%d,%d,%d,%d,%d,%d,%d|%d,%d,%d,%d,%d,%d,%d,%d,%d,%d*\\n",
              sizeof(base),
              int(&(b->x)), int(&(b->y)), int(&(b->a)), int(&(b->b)), int(&(b->c)),
              sizeof(hashtableentry),
              int(&(e->key)), int(&(e->data)), int(&(e->data.x)), int(&(e->data.y)), int(&(e->data.a)), int(&(e->data.b)), int(&(e->data.c)),
              sizeof(hashset::chain),
              int(&(c->elem)), int(&(c->next)), int(&(c->elem.key)), int(&(c->elem.data)), int(&(c->elem.data.x)), int(&(c->elem.data.y)), int(&(c->elem.data.a)), int(&(c->elem.data.b)), int(&(c->elem.data.c))
            );
          }
        };

        struct B { char buffer[62]; int last; char laster; char laster2; };

        struct Bits {
          unsigned short A : 1;
          unsigned short B : 1;
          unsigned short C : 1;
          unsigned short D : 1;
          unsigned short x1 : 1;
          unsigned short x2 : 1;
          unsigned short x3 : 1;
          unsigned short x4 : 1;
        };

        int main() {
          hashtable t;

          // Part 2 - the char[] should be compressed, BUT have a padding space at the end so the next
          // one is aligned properly. Also handle char; char; etc. properly.
          B *b = NULL;
          printf("*%d,%d,%d,%d,%d,%d,%d,%d,%d*\\n", int(b), int(&(b->buffer)), int(&(b->buffer[0])), int(&(b->buffer[1])), int(&(b->buffer[2])),
                                                    int(&(b->last)), int(&(b->laster)), int(&(b->laster2)), sizeof(B));

          // Part 3 - bitfields, and small structures
          Bits *b2 = NULL;
          printf("*%d*\\n", sizeof(Bits));

          return 0;
        }
        '''
      if Settings.QUANTUM_SIZE == 1:
        # Compressed memory. Note that sizeof() does give the fat sizes, however!
        self.do_run(src, '*16,0,1,2,2,3|20,0,1,1,2,3,3,4|24,0,5,0,1,1,2,3,3,4*\n*0,0,0,1,2,62,63,64,72*\n*2*')
      else:
        # Bloated memory; same layout as C/C++
        self.do_run(src, '*16,0,4,8,8,12|20,0,4,4,8,12,12,16|24,0,20,0,4,4,8,12,12,16*\n*0,0,0,1,2,64,68,69,72*\n*2*')

  def test_runtimelink(self):
    return self.skip('BUILD_AS_SHARED_LIB=2 is deprecated')
    if Building.LLVM_OPTS: return self.skip('LLVM opts will optimize printf into puts in the parent, and the child will still look for puts')
    if Settings.ASM_JS: return self.skip('asm does not support runtime linking')

    main, supp = self.setup_runtimelink_test()

    self.banned_js_engines = [NODE_JS] # node's global scope behaves differently than everything else, needs investigation FIXME
    Settings.LINKABLE = 1
    Settings.BUILD_AS_SHARED_LIB = 2
    Settings.NAMED_GLOBALS = 1

    self.build(supp, self.get_dir(), self.in_dir('supp.cpp'))
    shutil.move(self.in_dir('supp.cpp.o.js'), self.in_dir('liblib.so'))
    Settings.BUILD_AS_SHARED_LIB = 0

    Settings.RUNTIME_LINKED_LIBS = ['liblib.so'];
    self.do_run(main, 'supp: 54,2\nmain: 56\nsupp see: 543\nmain see: 76\nok.')

  def can_dlfcn(self):
    if self.emcc_args and '--memory-init-file' in self.emcc_args:
      for i in range(len(self.emcc_args)):
        if self.emcc_args[i] == '--memory-init-file':
          self.emcc_args = self.emcc_args[:i] + self.emcc_args[i+2:]
          break

    if Settings.ASM_JS:
      Settings.DLOPEN_SUPPORT = 1
    else:
      Settings.NAMED_GLOBALS = 1

    if not self.is_le32():
      self.skip('need le32 for dlfcn support')
      return False
    else:
      return True

  def prep_dlfcn_lib(self):
    if Settings.ASM_JS:
      Settings.MAIN_MODULE = 0
      Settings.SIDE_MODULE = 1
    else:
      Settings.BUILD_AS_SHARED_LIB = 1
      Settings.INCLUDE_FULL_LIBRARY = 0

  def prep_dlfcn_main(self):
    if Settings.ASM_JS:
      Settings.MAIN_MODULE = 1
      Settings.SIDE_MODULE = 0
    else:
      Settings.BUILD_AS_SHARED_LIB = 0
      Settings.INCLUDE_FULL_LIBRARY = 1

  dlfcn_post_build = '''
def process(filename):
  src = open(filename, 'r').read().replace(
    '// {{PRE_RUN_ADDITIONS}}',
    "FS.createLazyFile('/', 'liblib.so', 'liblib.so', true, false);"
  )
  open(filename, 'w').write(src)
'''

  def test_dlfcn_basic(self):
    if not self.can_dlfcn(): return

    self.prep_dlfcn_lib()
    lib_src = '''
      #include <cstdio>

      class Foo {
      public:
        Foo() {
          printf("Constructing lib object.\\n");
        }
      };

      Foo global;
      '''
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.cpp')
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    src = '''
      #include <cstdio>
      #include <dlfcn.h>

      class Bar {
      public:
        Bar() {
          printf("Constructing main object.\\n");
        }
      };

      Bar global;

      int main() {
        dlopen("liblib.so", RTLD_NOW);
        return 0;
      }
      '''
    self.do_run(src, 'Constructing main object.\nConstructing lib object.\n',
                post_build=self.dlfcn_post_build)

  def test_dlfcn_qsort(self):
    if not self.can_dlfcn(): return

    if Settings.USE_TYPED_ARRAYS == 2:
      Settings.CORRECT_SIGNS = 1 # Needed for unsafe optimizations

    self.prep_dlfcn_lib()
    Settings.EXPORTED_FUNCTIONS = ['_get_cmp']
    lib_src = '''
      int lib_cmp(const void* left, const void* right) {
        const int* a = (const int*) left;
        const int* b = (const int*) right;
        if(*a > *b) return 1;
        else if(*a == *b) return  0;
        else return -1;
      }

      typedef int (*CMP_TYPE)(const void*, const void*);

      extern "C" CMP_TYPE get_cmp() {
        return lib_cmp;
      }
      '''
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.cpp')
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    Settings.EXPORTED_FUNCTIONS = ['_main', '_malloc']
    src = '''
      #include <stdio.h>
      #include <stdlib.h>
      #include <dlfcn.h>

      typedef int (*CMP_TYPE)(const void*, const void*);

      int main_cmp(const void* left, const void* right) {
        const int* a = (const int*) left;
        const int* b = (const int*) right;
        if(*a < *b) return 1;
        else if(*a == *b) return  0;
        else return -1;
      }

      int main() {
        void* lib_handle;
        CMP_TYPE (*getter_ptr)();
        CMP_TYPE lib_cmp_ptr;
        int arr[5] = {4, 2, 5, 1, 3};

        qsort((void*)arr, 5, sizeof(int), main_cmp);
        printf("Sort with main comparison: ");
        for (int i = 0; i < 5; i++) {
          printf("%d ", arr[i]);
        }
        printf("\\n");

        lib_handle = dlopen("liblib.so", RTLD_NOW);
        if (lib_handle == NULL) {
          printf("Could not load lib.\\n");
          return 1;
        }
        getter_ptr = (CMP_TYPE (*)()) dlsym(lib_handle, "get_cmp");
        if (getter_ptr == NULL) {
          printf("Could not find func.\\n");
          return 1;
        }
        lib_cmp_ptr = getter_ptr();
        qsort((void*)arr, 5, sizeof(int), lib_cmp_ptr);
        printf("Sort with lib comparison: ");
        for (int i = 0; i < 5; i++) {
          printf("%d ", arr[i]);
        }
        printf("\\n");

        return 0;
      }
      '''
    self.do_run(src, 'Sort with main comparison: 5 4 3 2 1 *Sort with lib comparison: 1 2 3 4 5 *',
                output_nicerizer=lambda x, err: x.replace('\n', '*'),
                post_build=self.dlfcn_post_build)

    if Settings.ASM_JS and os.path.exists(SPIDERMONKEY_ENGINE[0]):
      out = run_js('liblib.so', engine=SPIDERMONKEY_ENGINE, full_output=True, stderr=STDOUT)
      if 'asm' in out:
        self.validate_asmjs(out)

  def test_dlfcn_data_and_fptr(self):
    if Settings.ASM_JS: return self.skip('this is not a valid case - libraries should not be able to access their parents globals willy nilly')
    if not self.can_dlfcn(): return

    if Building.LLVM_OPTS: return self.skip('LLVM opts will optimize out parent_func')

    self.prep_dlfcn_lib()
    lib_src = '''
      #include <stdio.h>

      int global = 42;

      extern void parent_func(); // a function that is defined in the parent

      void lib_fptr() {
        printf("Second calling lib_fptr from main.\\n");
        parent_func();
        // call it also through a pointer, to check indexizing
        void (*p_f)();
        p_f = parent_func;
        p_f();
      }

      extern "C" void (*func(int x, void(*fptr)()))() {
        printf("In func: %d\\n", x);
        fptr();
        return lib_fptr;
      }
      '''
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.cpp')
    Settings.EXPORTED_FUNCTIONS = ['_func']
    Settings.EXPORTED_GLOBALS = ['_global']
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    Settings.LINKABLE = 1
    src = '''
      #include <stdio.h>
      #include <dlfcn.h>
      #include <emscripten.h>

      typedef void (*FUNCTYPE(int, void(*)()))();

      FUNCTYPE func;

      void EMSCRIPTEN_KEEPALIVE parent_func() {
        printf("parent_func called from child\\n");
      }

      void main_fptr() {
        printf("First calling main_fptr from lib.\\n");
      }

      int main() {
        void* lib_handle;
        FUNCTYPE* func_fptr;

        // Test basic lib loading.
        lib_handle = dlopen("liblib.so", RTLD_NOW);
        if (lib_handle == NULL) {
          printf("Could not load lib.\\n");
          return 1;
        }

        // Test looked up function.
        func_fptr = (FUNCTYPE*) dlsym(lib_handle, "func");
        // Load twice to test cache.
        func_fptr = (FUNCTYPE*) dlsym(lib_handle, "func");
        if (func_fptr == NULL) {
          printf("Could not find func.\\n");
          return 1;
        }

        // Test passing function pointers across module bounds.
        void (*fptr)() = func_fptr(13, main_fptr);
        fptr();

        // Test global data.
        int* global = (int*) dlsym(lib_handle, "global");
        if (global == NULL) {
          printf("Could not find global.\\n");
          return 1;
        }

        printf("Var: %d\\n", *global);

        return 0;
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_main']
    Settings.EXPORTED_GLOBALS = []
    self.do_run(src, 'In func: 13*First calling main_fptr from lib.*Second calling lib_fptr from main.*parent_func called from child*parent_func called from child*Var: 42*',
                 output_nicerizer=lambda x, err: x.replace('\n', '*'),
                 post_build=self.dlfcn_post_build)

  def test_dlfcn_alias(self):
    if Settings.ASM_JS: return self.skip('this is not a valid case - libraries should not be able to access their parents globals willy nilly')

    Settings.LINKABLE = 1
    Settings.NAMED_GLOBALS = 1

    if Building.LLVM_OPTS == 2: return self.skip('LLVM LTO will optimize away stuff we expect from the shared library')

    lib_src = r'''
      #include <stdio.h>
      extern int parent_global;
      extern "C" void func() {
        printf("Parent global: %d.\n", parent_global);
      }
      '''
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.cpp')
    Settings.BUILD_AS_SHARED_LIB = 1
    Settings.EXPORTED_FUNCTIONS = ['_func']
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    src = r'''
      #include <dlfcn.h>

      int parent_global = 123;

      int main() {
        void* lib_handle;
        void (*fptr)();

        lib_handle = dlopen("liblib.so", RTLD_NOW);
        fptr = (void (*)())dlsym(lib_handle, "func");
        fptr();
        parent_global = 456;
        fptr();

        return 0;
      }
      '''
    Settings.BUILD_AS_SHARED_LIB = 0
    Settings.INCLUDE_FULL_LIBRARY = 1
    Settings.EXPORTED_FUNCTIONS = ['_main']
    self.do_run(src, 'Parent global: 123.*Parent global: 456.*',
                output_nicerizer=lambda x, err: x.replace('\n', '*'),
                post_build=self.dlfcn_post_build,
                extra_emscripten_args=['-H', 'libc/fcntl.h,libc/sys/unistd.h,poll.h,libc/math.h,libc/time.h,libc/langinfo.h'])
    Settings.INCLUDE_FULL_LIBRARY = 0

  def test_dlfcn_varargs(self):
    if Settings.ASM_JS: return self.skip('this is not a valid case - libraries should not be able to access their parents globals willy nilly')

    if not self.can_dlfcn(): return

    Settings.LINKABLE = 1

    if Building.LLVM_OPTS == 2: return self.skip('LLVM LTO will optimize things that prevent shared objects from working')
    if Settings.QUANTUM_SIZE == 1: return self.skip('FIXME: Add support for this')

    self.prep_dlfcn_lib()
    lib_src = r'''
      void print_ints(int n, ...);
      extern "C" void func() {
        print_ints(2, 13, 42);
      }
      '''
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.cpp')
    Settings.EXPORTED_FUNCTIONS = ['_func']
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    src = r'''
      #include <stdarg.h>
      #include <stdio.h>
      #include <dlfcn.h>
      #include <assert.h>

      void print_ints(int n, ...) {
        va_list args;
        va_start(args, n);
        for (int i = 0; i < n; i++) {
          printf("%d\n", va_arg(args, int));
        }
        va_end(args);
      }

      int main() {
        void* lib_handle;
        void (*fptr)();

        print_ints(2, 100, 200);

        lib_handle = dlopen("liblib.so", RTLD_NOW);
        assert(lib_handle);
        fptr = (void (*)())dlsym(lib_handle, "func");
        fptr();

        return 0;
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_main']
    self.do_run(src, '100\n200\n13\n42\n',
                post_build=self.dlfcn_post_build)

  def test_dlfcn_self(self):
    if Settings.USE_TYPED_ARRAYS == 1: return self.skip('Does not work with USE_TYPED_ARRAYS=1')
    Settings.DLOPEN_SUPPORT = 1

    src = r'''
#include <stdio.h>
#include <dlfcn.h>
#include <emscripten.h>

int EMSCRIPTEN_KEEPALIVE global = 123;

extern "C" EMSCRIPTEN_KEEPALIVE void foo(int x) {
printf("%d\n", x);
}

extern "C" EMSCRIPTEN_KEEPALIVE void repeatable() {
void* self = dlopen(NULL, RTLD_LAZY);
int* global_ptr = (int*)dlsym(self, "global");
void (*foo_ptr)(int) = (void (*)(int))dlsym(self, "foo");
foo_ptr(*global_ptr);
dlclose(self);
}

int main() {
repeatable();
repeatable();
return 0;
}'''
    def post(filename):
      with open(filename) as f:
        for line in f:
          if 'var SYMBOL_TABLE' in line:
            table = line
            break
        else:
          raise Exception('Could not find symbol table!')
      table = table[table.find('{'):table.rfind('}')+1]
      # ensure there aren't too many globals; we don't want unnamed_addr
      assert table.count(',') <= 4
    self.do_run(src, '123\n123', post_build=(None, post))


  def test_dlfcn_unique_sig(self):
    if not self.can_dlfcn(): return

    self.prep_dlfcn_lib()
    lib_src = '''
      #include <stdio.h>

      int myfunc(int a, int b, int c, int d, int e, int f, int g, int h, int i, int j, int k, int l, int m) {
        return 13;
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_myfunc']
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.c')
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    src = '''
      #include <assert.h>
      #include <stdio.h>
      #include <dlfcn.h>

      typedef int (*FUNCTYPE)(int, int, int, int, int, int, int, int, int, int, int, int, int);

      int main() {
        void *lib_handle;
        FUNCTYPE func_ptr;

        lib_handle = dlopen("liblib.so", RTLD_NOW);
        assert(lib_handle != NULL);

        func_ptr = (FUNCTYPE)dlsym(lib_handle, "myfunc");
        assert(func_ptr != NULL);
        assert(func_ptr(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0) == 13);

        puts("success");

        return 0;
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_main', '_malloc']
    self.do_run(src, 'success', force_c=True, post_build=self.dlfcn_post_build)

  def test_dlfcn_stacks(self):
    if not self.can_dlfcn(): return

    self.prep_dlfcn_lib()
    lib_src = '''
      #include <assert.h>
      #include <stdio.h>
      #include <string.h>

      int myfunc(const char *input) {
        char bigstack[1024] = { 0 };

        // make sure we didn't just trample the stack!
        assert(!strcmp(input, "foobar"));

        snprintf(bigstack, sizeof(bigstack), input);
        return strlen(bigstack);
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_myfunc']
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.c')
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    src = '''
      #include <assert.h>
      #include <stdio.h>
      #include <dlfcn.h>

      typedef int (*FUNCTYPE)(const char *);

      int main() {
        void *lib_handle;
        FUNCTYPE func_ptr;
        char str[128];

        snprintf(str, sizeof(str), "foobar");

        lib_handle = dlopen("liblib.so", RTLD_NOW);
        assert(lib_handle != NULL);

        func_ptr = (FUNCTYPE)dlsym(lib_handle, "myfunc");
        assert(func_ptr != NULL);
        assert(func_ptr(str) == 6);

        puts("success");

        return 0;
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_main', '_malloc']
    self.do_run(src, 'success', force_c=True, post_build=self.dlfcn_post_build)

  def test_dlfcn_funcs(self):
    if not self.can_dlfcn(): return

    self.prep_dlfcn_lib()
    lib_src = r'''
      #include <assert.h>
      #include <stdio.h>
      #include <string.h>

      typedef void (*voidfunc)();
      typedef void (*intfunc)(int);

      void callvoid(voidfunc f) { f(); }
      void callint(voidfunc f, int x) { f(x); }

      void void_0() { printf("void 0\n"); }
      void void_1() { printf("void 1\n"); }
      voidfunc getvoid(int i) {
        switch(i) {
          case 0: return void_0;
          case 1: return void_1;
          default: return NULL;
        }
      }

      void int_0(int x) { printf("int 0 %d\n", x); }
      void int_1(int x) { printf("int 1 %d\n", x); }
      intfunc getint(int i) {
        switch(i) {
          case 0: return int_0;
          case 1: return int_1;
          default: return NULL;
        }
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_callvoid', '_callint', '_getvoid', '_getint']
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.c')
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    src = r'''
      #include <assert.h>
      #include <stdio.h>
      #include <dlfcn.h>

      typedef void (*voidfunc)();
      typedef void (*intfunc)(int);

      typedef void (*voidcaller)(voidfunc);
      typedef void (*intcaller)(intfunc, int);

      typedef voidfunc (*voidgetter)(int);
      typedef intfunc (*intgetter)(int);

      void void_main() { printf("main.\n"); }
      void int_main(int x) { printf("main %d\n", x); }

      int main() {
        printf("go\n");
        void *lib_handle;
        lib_handle = dlopen("liblib.so", RTLD_NOW);
        assert(lib_handle != NULL);

        voidcaller callvoid = (voidcaller)dlsym(lib_handle, "callvoid");
        assert(callvoid != NULL);
        callvoid(void_main);

        intcaller callint = (intcaller)dlsym(lib_handle, "callint");
        assert(callint != NULL);
        callint(int_main, 201);

        voidgetter getvoid = (voidgetter)dlsym(lib_handle, "getvoid");
        assert(getvoid != NULL);
        callvoid(getvoid(0));
        callvoid(getvoid(1));

        intgetter getint = (intgetter)dlsym(lib_handle, "getint");
        assert(getint != NULL);
        callint(getint(0), 54);
        callint(getint(1), 9000);

        assert(getint(1000) == NULL);

        puts("ok");
        return 0;
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_main', '_malloc']
    self.do_run(src, '''go
main.
main 201
void 0
void 1
int 0 54
int 1 9000
ok
''', force_c=True, post_build=self.dlfcn_post_build)

  def test_dlfcn_mallocs(self):
    if not Settings.ASM_JS: return self.skip('needs asm')

    if not self.can_dlfcn(): return

    Settings.TOTAL_MEMORY = 64*1024*1024 # will be exhausted without functional malloc/free

    self.prep_dlfcn_lib()
    lib_src = r'''
      #include <assert.h>
      #include <stdio.h>
      #include <string.h>
      #include <stdlib.h>

      void *mallocproxy(int n) { return malloc(n); }
      void freeproxy(void *p) { free(p); }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_mallocproxy', '_freeproxy']
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.c')
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    src = open(path_from_root('tests', 'dlmalloc_proxy.c')).read()
    Settings.EXPORTED_FUNCTIONS = ['_main', '_malloc', '_free']
    self.do_run(src, '''*294,153*''', force_c=True, post_build=self.dlfcn_post_build)

  def test_dlfcn_longjmp(self):
    if not self.can_dlfcn(): return

    self.prep_dlfcn_lib()
    lib_src = r'''
      #include <setjmp.h>

      void jumpy(jmp_buf buf) {
        static int i = 0;
        i++;
        if (i == 10) longjmp(buf, i);
        printf("pre %d\n", i);
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_jumpy']
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.c')
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    src = r'''
      #include <assert.h>
      #include <stdio.h>
      #include <dlfcn.h>
      #include <setjmp.h>

      typedef void (*jumpfunc)(jmp_buf);

      int main() {
        printf("go!\n");

        void *lib_handle;
        lib_handle = dlopen("liblib.so", RTLD_NOW);
        assert(lib_handle != NULL);

        jumpfunc jumpy = (jumpfunc)dlsym(lib_handle, "jumpy");
        assert(jumpy);

        jmp_buf buf;
        int jmpval = setjmp(buf);
        if (jmpval == 0) {
          while (1) jumpy(buf);
        } else {
          printf("out!\n");
        }

        return 0;
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_main', '_malloc', '_free']
    self.do_run(src, '''go!
pre 1
pre 2
pre 3
pre 4
pre 5
pre 6
pre 7
pre 8
pre 9
out!
''', post_build=self.dlfcn_post_build, force_c=True)

  def zzztest_dlfcn_exceptions(self): # TODO: make this work. need to forward tempRet0 across modules
    if not self.can_dlfcn(): return

    Settings.DISABLE_EXCEPTION_CATCHING = 0

    self.prep_dlfcn_lib()
    lib_src = r'''
      extern "C" {
      int ok() {
        return 65;
      }
      int fail() {
        throw 123;
      }
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_ok', '_fail']
    dirname = self.get_dir()
    filename = os.path.join(dirname, 'liblib.cpp')
    self.build(lib_src, dirname, filename)
    shutil.move(filename + '.o.js', os.path.join(dirname, 'liblib.so'))

    self.prep_dlfcn_main()
    src = r'''
      #include <assert.h>
      #include <stdio.h>
      #include <dlfcn.h>

      typedef int (*intfunc)();

      int main() {
        printf("go!\n");

        void *lib_handle;
        lib_handle = dlopen("liblib.so", RTLD_NOW);
        assert(lib_handle != NULL);

        intfunc okk = (intfunc)dlsym(lib_handle, "ok");
        intfunc faill = (intfunc)dlsym(lib_handle, "fail");
        assert(okk && faill);

        try {
          printf("ok: %d\n", okk());
        } catch(...) {
          printf("wha\n");
        }

        try {
          printf("fail: %d\n", faill());
        } catch(int x) {
          printf("int %d\n", x);
        }

        try {
          printf("fail: %d\n", faill());
        } catch(double x) {
          printf("caught %f\n", x);
        }

        return 0;
      }
      '''
    Settings.EXPORTED_FUNCTIONS = ['_main', '_malloc', '_free']
    self.do_run(src, '''go!
ok: 65
int 123
ok
''', post_build=self.dlfcn_post_build)

  def test_rand(self):
    return self.skip('rand() is now random') # FIXME

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      int main() {
        printf("%d\n", rand());
        printf("%d\n", rand());

        srand(123);
        printf("%d\n", rand());
        printf("%d\n", rand());
        srand(123);
        printf("%d\n", rand());
        printf("%d\n", rand());

        unsigned state = 0;
        int r;
        r = rand_r(&state);
        printf("%d, %u\n", r, state);
        r = rand_r(&state);
        printf("%d, %u\n", r, state);
        state = 0;
        r = rand_r(&state);
        printf("%d, %u\n", r, state);

        return 0;
      }
      '''
    expected = '''
      1250496027
      1116302336
      440917656
      1476150784
      440917656
      1476150784
      12345, 12345
      1406932606, 3554416254
      12345, 12345
      '''
    self.do_run(src, re.sub(r'(^|\n)\s+', r'\1', expected))

  def test_strtod(self):
    if self.emcc_args is None: return self.skip('needs emcc for libc')

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      int main() {
        char* endptr;

        printf("\n");
        printf("%g\n", strtod("0", &endptr));
        printf("%g\n", strtod("0.", &endptr));
        printf("%g\n", strtod("0.0", &endptr));
        printf("%g\n", strtod("-0.0", &endptr));
        printf("%g\n", strtod("1", &endptr));
        printf("%g\n", strtod("1.", &endptr));
        printf("%g\n", strtod("1.0", &endptr));
        printf("%g\n", strtod("z1.0", &endptr));
        printf("%g\n", strtod("0.5", &endptr));
        printf("%g\n", strtod(".5", &endptr));
        printf("%g\n", strtod(".a5", &endptr));
        printf("%g\n", strtod("123", &endptr));
        printf("%g\n", strtod("123.456", &endptr));
        printf("%g\n", strtod("-123.456", &endptr));
        printf("%g\n", strtod("1234567891234567890", &endptr));
        printf("%g\n", strtod("1234567891234567890e+50", &endptr));
        printf("%g\n", strtod("84e+220", &endptr));
        printf("%g\n", strtod("123e-50", &endptr));
        printf("%g\n", strtod("123e-250", &endptr));
        printf("%g\n", strtod("123e-450", &endptr));

        char str[] = "  12.34e56end";
        printf("%g\n", strtod(str, &endptr));
        printf("%d\n", endptr - str);
        printf("%g\n", strtod("84e+420", &endptr));

        printf("%.12f\n", strtod("1.2345678900000000e+08", NULL));

        return 0;
      }
      '''
    expected = '''
      0
      0
      0
      -0
      1
      1
      1
      0
      0.5
      0.5
      0
      123
      123.456
      -123.456
      1.23457e+18
      1.23457e+68
      8.4e+221
      1.23e-48
      1.23e-248
      0
      1.234e+57
      10
      inf
      123456789.000000000000
      '''

    self.do_run(src, re.sub(r'\n\s+', '\n', expected))
    self.do_run(src.replace('strtod', 'strtold'), re.sub(r'\n\s+', '\n', expected)) # XXX add real support for long double

  def test_strtok(self):
    src = r'''
      #include<stdio.h>
      #include<string.h>

      int main() {
        char test[80], blah[80];
        char *sep = "\\/:;=-";
        char *word, *phrase, *brkt, *brkb;

        strcpy(test, "This;is.a:test:of=the/string\\tokenizer-function.");

        for (word = strtok_r(test, sep, &brkt); word; word = strtok_r(NULL, sep, &brkt)) {
          strcpy(blah, "blah:blat:blab:blag");
          for (phrase = strtok_r(blah, sep, &brkb); phrase; phrase = strtok_r(NULL, sep, &brkb)) {
            printf("at %s:%s\n", word, phrase);
          }
        }
        return 0;
      }
    '''

    expected = '''at This:blah
at This:blat
at This:blab
at This:blag
at is.a:blah
at is.a:blat
at is.a:blab
at is.a:blag
at test:blah
at test:blat
at test:blab
at test:blag
at of:blah
at of:blat
at of:blab
at of:blag
at the:blah
at the:blat
at the:blab
at the:blag
at string:blah
at string:blat
at string:blab
at string:blag
at tokenizer:blah
at tokenizer:blat
at tokenizer:blab
at tokenizer:blag
at function.:blah
at function.:blat
at function.:blab
at function.:blag
'''
    self.do_run(src, expected)

  def test_parseInt(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('i64 mode 1 requires ta2')
    if Settings.QUANTUM_SIZE == 1: return self.skip('Q1 and I64_1 do not mix well yet')
    src = open(path_from_root('tests', 'parseInt', 'src.c'), 'r').read()
    expected = open(path_from_root('tests', 'parseInt', 'output.txt'), 'r').read()
    self.do_run(src, expected)

  def test_transtrcase(self):
    src = '''
      #include <stdio.h>
      #include <string.h>
      int main()  {
        char szToupr[] = "hello, ";
        char szTolwr[] = "EMSCRIPTEN";
        strupr(szToupr);
        strlwr(szTolwr);
        printf(szToupr);
        printf(szTolwr);
        return 0;
      }
      '''
    self.do_run(src, 'HELLO, emscripten')

  def test_printf(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('i64 mode 1 requires ta2')
    self.banned_js_engines = [NODE_JS, V8_ENGINE] # SpiderMonkey and V8 do different things to float64 typed arrays, un-NaNing, etc.
    src = open(path_from_root('tests', 'printf', 'test.c'), 'r').read()
    expected = [open(path_from_root('tests', 'printf', 'output.txt'), 'r').read(),
                open(path_from_root('tests', 'printf', 'output_i64_1.txt'), 'r').read()]
    self.do_run(src, expected)

  def test_printf_2(self):
    src = r'''
      #include <stdio.h>

      int main() {
        char c = '1';
        short s = 2;
        int i = 3;
        long long l = 4;
        float f = 5.5;
        double d = 6.6;

        printf("%c,%hd,%d,%lld,%.1f,%.1llf\n", c, s, i, l, f, d);
        printf("%#x,%#x\n", 1, 0);

        return 0;
      }
      '''
    self.do_run(src, '1,2,3,4,5.5,6.6\n0x1,0\n')

  def test_vprintf(self):
    src = r'''
      #include <stdio.h>
      #include <stdarg.h>

      void print(char* format, ...) {
        va_list args;
        va_start (args, format);
        vprintf (format, args);
        va_end (args);
      }

      int main () {
         print("Call with %d variable argument.\n", 1);
         print("Call with %d variable %s.\n", 2, "arguments");

         return 0;
      }
      '''
    expected = '''
      Call with 1 variable argument.
      Call with 2 variable arguments.
      '''
    self.do_run(src, re.sub('(^|\n)\s+', '\\1', expected))

  def test_vsnprintf(self):
    if self.emcc_args is None: return self.skip('needs i64 math')

    src = r'''
      #include <stdio.h>
      #include <stdarg.h>
      #include <stdint.h>

      void printy(const char *f, ...)
      {
        char buffer[256];
        va_list args;
        va_start(args, f);
        vsnprintf(buffer, 256, f, args);
        puts(buffer);
        va_end(args);
      }

      int main(int argc, char **argv) {
        int64_t x = argc - 1;
        int64_t y = argc - 1 + 0x400000;
        if (x % 3 == 2) y *= 2;

        printy("0x%llx_0x%llx", x, y);
        printy("0x%llx_0x%llx", x, x);
        printy("0x%llx_0x%llx", y, x);
        printy("0x%llx_0x%llx", y, y);

        {
          uint64_t A = 0x800000;
          uint64_t B = 0x800000000000ULL;
          printy("0x%llx_0x%llx", A, B);
        }
        {
          uint64_t A = 0x800;
          uint64_t B = 0x12340000000000ULL;
          printy("0x%llx_0x%llx", A, B);
        }
        {
          uint64_t A = 0x000009182746756;
          uint64_t B = 0x192837465631ACBDULL;
          printy("0x%llx_0x%llx", A, B);
        }

        return 0;
      }
    '''
    self.do_run(src, '''0x0_0x400000
0x0_0x0
0x400000_0x0
0x400000_0x400000
0x800000_0x800000000000
0x800_0x12340000000000
0x9182746756_0x192837465631acbd
''')

  def test_printf_more(self):
    src = r'''
      #include <stdio.h>
      int main()  {
        int size = snprintf(NULL, 0, "%s %d %.2f\n", "me and myself", 25, 1.345);
        char buf[size];
        snprintf(buf, size, "%s %d %.2f\n", "me and myself", 25, 1.345);
        printf("%d : %s\n", size, buf);
        char *buff = NULL;
        asprintf(&buff, "%d waka %d\n", 21, 95);
        puts(buff);
        return 0;
      }
      '''
    self.do_run(src, '22 : me and myself 25 1.34\n21 waka 95\n')

  def test_perrar(self):
    src = r'''
      #include <sys/types.h>
      #include <sys/stat.h>
      #include <fcntl.h>
      #include <stdio.h>

      int main( int argc, char** argv ){
        int retval = open( "NonExistingFile", O_RDONLY );
        if( retval == -1 )
        perror( "Cannot open NonExistingFile" );
        return 0;
      }
      '''
    self.do_run(src, 'Cannot open NonExistingFile: No such file or directory\n')

  def test_atoX(self):
    if self.emcc_args is None: return self.skip('requires ta2')

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      int main () {
        printf("%d*", atoi(""));
        printf("%d*", atoi("a"));
        printf("%d*", atoi(" b"));
        printf("%d*", atoi(" c "));
        printf("%d*", atoi("6"));
        printf("%d*", atoi(" 5"));
        printf("%d*", atoi("4 "));
        printf("%d*", atoi("3 6"));
        printf("%d*", atoi(" 3 7"));
        printf("%d*", atoi("9 d"));
        printf("%d\n", atoi(" 8 e"));
        printf("%d*", atol(""));
        printf("%d*", atol("a"));
        printf("%d*", atol(" b"));
        printf("%d*", atol(" c "));
        printf("%d*", atol("6"));
        printf("%d*", atol(" 5"));
        printf("%d*", atol("4 "));
        printf("%d*", atol("3 6"));
        printf("%d*", atol(" 3 7"));
        printf("%d*", atol("9 d"));
        printf("%d\n", atol(" 8 e"));
        printf("%lld*", atoll("6294967296"));
        printf("%lld*", atoll(""));
        printf("%lld*", atoll("a"));
        printf("%lld*", atoll(" b"));
        printf("%lld*", atoll(" c "));
        printf("%lld*", atoll("6"));
        printf("%lld*", atoll(" 5"));
        printf("%lld*", atoll("4 "));
        printf("%lld*", atoll("3 6"));
        printf("%lld*", atoll(" 3 7"));
        printf("%lld*", atoll("9 d"));
        printf("%lld\n", atoll(" 8 e"));
        return 0;
      }
      '''
    self.do_run(src, '0*0*0*0*6*5*4*3*3*9*8\n0*0*0*0*6*5*4*3*3*9*8\n6294967296*0*0*0*0*6*5*4*3*3*9*8\n')

  def test_strstr(self):
    src = r'''
      #include <stdio.h>
      #include <string.h>

      int main()
      {
        printf("%d\n", !!strstr("\\n", "\\n"));
        printf("%d\n", !!strstr("cheezy", "ez"));
        printf("%d\n", !!strstr("cheeezy", "ez"));
        printf("%d\n", !!strstr("cheeeeeeeeeezy", "ez"));
        printf("%d\n", !!strstr("cheeeeeeeeee1zy", "ez"));
        printf("%d\n", !!strstr("che1ezy", "ez"));
        printf("%d\n", !!strstr("che1ezy", "che"));
        printf("%d\n", !!strstr("ce1ezy", "che"));
        printf("%d\n", !!strstr("ce1ezy", "ezy"));
        printf("%d\n", !!strstr("ce1ezyt", "ezy"));
        printf("%d\n", !!strstr("ce1ez1y", "ezy"));
        printf("%d\n", !!strstr("cheezy", "a"));
        printf("%d\n", !!strstr("cheezy", "b"));
        printf("%d\n", !!strstr("cheezy", "c"));
        printf("%d\n", !!strstr("cheezy", "d"));
        printf("%d\n", !!strstr("cheezy", "g"));
        printf("%d\n", !!strstr("cheezy", "h"));
        printf("%d\n", !!strstr("cheezy", "i"));
        printf("%d\n", !!strstr("cheezy", "e"));
        printf("%d\n", !!strstr("cheezy", "x"));
        printf("%d\n", !!strstr("cheezy", "y"));
        printf("%d\n", !!strstr("cheezy", "z"));
        printf("%d\n", !!strstr("cheezy", "_"));

        const char *str = "a big string";
        printf("%d\n", strstr(str, "big") - str);
        return 0;
      }
    '''
    self.do_run(src, '''1
1
1
1
0
1
1
0
1
1
0
0
0
1
0
0
1
0
1
0
1
1
0
2
''')

  def test_sscanf(self):
    if self.emcc_args is None: return self.skip('needs emcc for libc')

    src = r'''
      #include <stdio.h>
      #include <string.h>
      #include <stdlib.h>

      int main () {
        #define CHECK(str) \
        { \
          char name[1000]; \
          memset(name, 0, 1000); \
          int prio = 99; \
          sscanf(str, "%s %d", name, &prio); \
          printf("%s : %d\n", name, prio); \
        }
        CHECK("en-us 2");
        CHECK("en-r");
        CHECK("en 3");

        printf("%f, %f\n", atof("1.234567"), atof("cheez"));

        char float_formats[] = "fegE";
        char format[] = "%_";
        for(int i = 0; i < 4; ++i) {
          format[1] = float_formats[i];

          float n = -1;
          sscanf(" 2.8208", format, &n);
          printf("%.4f\n", n);

          float a = -1;
          sscanf("-3.03", format, &a);
          printf("%.4f\n", a);
        }

        char buffy[100];
        sscanf("cheez some thing moar 123\nyet more\n", "cheez %s", buffy);
        printf("|%s|\n", buffy);
        sscanf("cheez something\nmoar 123\nyet more\n", "cheez %s", buffy);
        printf("|%s|\n", buffy);
        sscanf("cheez somethingmoar\tyet more\n", "cheez %s", buffy);
        printf("|%s|\n", buffy);

        int numverts = -1;
        printf("%d\n", sscanf("	numverts 1499\n", " numverts %d", &numverts)); // white space is the same, even if tab vs space
        printf("%d\n", numverts);

        int index;
        float u, v;
        short start, count;
        printf("%d\n", sscanf("	vert 87 ( 0.481565 0.059481 ) 0 1\n", " vert %d ( %f %f ) %hu %hu", &index, &u, &v, &start, &count));
        printf("%d,%.6f,%.6f,%hu,%hu\n", index, u, v, start, count);

        int neg, neg2, neg3 = 0;
        printf("%d\n", sscanf("-123 -765 -34-6", "%d %u %d", &neg, &neg2, &neg3));
        printf("%d,%u,%d\n", neg, neg2, neg3);

        {
          int a = 0;
          sscanf("1", "%i", &a);
          printf("%i\n", a);
        }

        char buf1[100], buf2[100], buf3[100], buf4[100];

        int numItems = sscanf("level=4:ref=3", "%255[^:=]=%255[^:]:%255[^=]=%255c", buf1, buf2, buf3, buf4);
        printf("%d, %s, %s, %s, %s\n", numItems, buf1, buf2, buf3, buf4);

        numItems = sscanf("def|456", "%[a-z]|%[0-9]", buf1, buf2);
        printf("%d, %s, %s\n", numItems, buf1, buf2);

        numItems = sscanf("3-4,-ab", "%[-0-9],%[ab-z-]", buf1, buf2);
        printf("%d, %s, %s\n", numItems, buf1, buf2);

        numItems = sscanf("Hello,World", "%[A-Za-z],%[^0-9]", buf1, buf2);
        printf("%d, %s, %s\n", numItems, buf1, buf2);

        numItems = sscanf("Hello4711", "%[^0-9],%[^0-9]", buf1, buf2);
        printf("%d, %s\n", numItems, buf1);

        numItems = sscanf("JavaScript", "%4[A-Za-z]", buf1);
        printf("%d, %s\n", numItems, buf1);
    
        numItems = sscanf("[]", "%1[[]%1[]]", buf1, buf2);
        printf("%d, %s, %s\n", numItems, buf1, buf2);

        return 0;
      }
      '''
    self.do_run(src, 'en-us : 2\nen-r : 99\nen : 3\n1.234567, 0.000000\n2.8208\n-3.0300\n2.8208\n-3.0300\n2.8208\n-3.0300\n2.8208\n-3.0300\n|some|\n|something|\n|somethingmoar|\n' +
                     '1\n1499\n' +
                     '5\n87,0.481565,0.059481,0,1\n' +
                     '3\n-123,4294966531,-34\n' +
                     '1\n' +
                     '4, level, 4, ref, 3\n' +
                     '2, def, 456\n' +
                     '2, 3-4, -ab\n' +
                     '2, Hello, World\n' +
                     '1, Hello\n' +
                     '1, Java\n' +
                     '2, [, ]')

  def test_sscanf_2(self):
    # doubles
    if Settings.USE_TYPED_ARRAYS == 2:
      for ftype in ['float', 'double']:
        src = r'''
          #include <stdio.h>

          int main(){
              char strval1[] = "1.2345678901";
              char strval2[] = "1.23456789e5";
              char strval3[] = "1.23456789E5";
              char strval4[] = "1.2345678e-5";
              char strval5[] = "1.2345678E-5";
              double dblval = 1.2345678901;
              double tstval;

              sscanf(strval1, "%lf", &tstval);
              if(dblval != tstval) printf("FAIL: Values are not equal: %lf %lf\n", dblval, tstval);
              else printf("Pass: %lf %lf\n", tstval, dblval);

              sscanf(strval2, "%lf", &tstval);
              dblval = 123456.789;
              if(dblval != tstval) printf("FAIL: Values are not equal: %lf %lf\n", dblval, tstval);
              else printf("Pass: %lf %lf\n", tstval, dblval);

              sscanf(strval3, "%lf", &tstval);
              dblval = 123456.789;
              if(dblval != tstval) printf("FAIL: Values are not equal: %lf %lf\n", dblval, tstval);
              else printf("Pass: %lf %lf\n", tstval, dblval);

              sscanf(strval4, "%lf", &tstval);
              dblval = 0.000012345678;
              if(dblval != tstval) printf("FAIL: Values are not equal: %lf %lf\n", dblval, tstval);
              else printf("Pass: %lf %lf\n", tstval, dblval);

              sscanf(strval5, "%lf", &tstval);
              dblval = 0.000012345678;
              if(dblval != tstval) printf("FAIL: Values are not equal: %lf %lf\n", dblval, tstval);
              else printf("Pass: %lf %lf\n", tstval, dblval);

              return 0;
          }
        '''
        if ftype == 'float':
          self.do_run(src.replace('%lf', '%f').replace('double', 'float'), '''Pass: 1.234568 1.234568
Pass: 123456.789063 123456.789063
Pass: 123456.789063 123456.789063
Pass: 0.000012 0.000012
Pass: 0.000012 0.000012''')
        else:
          self.do_run(src, '''Pass: 1.234568 1.234568
Pass: 123456.789000 123456.789000
Pass: 123456.789000 123456.789000
Pass: 0.000012 0.000012
Pass: 0.000012 0.000012''')

  def test_sscanf_n(self):
    src = r'''
      #include<stdio.h>
      int main() {
        char *line = "version 1.0";
        int i, l, lineno;
        char word[80];
        if (sscanf(line, "%s%n", word, &l) != 1) {
            printf("Header format error, line %d\n", lineno);
        }
        printf("[DEBUG] word 1: %s, l: %d\n", word, l);

        int x = sscanf("one %n two", "%s %n", word, &l);
        printf("%d,%s,%d\n", x, word, l);
        {
          int a, b, c, count;
          count = sscanf("12345 6789", "%d %n%d", &a, &b, &c);
          printf("%i %i %i %i\n", count, a, b, c);
        }
        return 0;
      }
    '''
    self.do_run(src, '''[DEBUG] word 1: version, l: 7\n1,one,4\n2 12345 6 6789\n''')

  def test_sscanf_whitespace(self):
    src = r'''
      #include<stdio.h>

      int main() {
        short int x;
        short int y;

        const char* buffer[] = {
          "173,16",
          "    16,173",
          "183,   173",
          "  17,   287",
          " 98,  123,   "
        };

        for (int i=0; i<5; ++i) {
          sscanf(buffer[i], "%hd,%hd", &x, &y);
          printf("%d:%d,%d ", i, x, y);
        }

        return 0;
      }
    '''
    self.do_run(src, '''0:173,16 1:16,173 2:183,173 3:17,287 4:98,123''')

  def test_sscanf_other_whitespace(self):
    Settings.SAFE_HEAP = 0 # use i16s in printf

    src = r'''
      #include<stdio.h>

      int main() {
        short int x;
        short int y;

        const char* buffer[] = {
          "\t2\t3\t", /* TAB - horizontal tab */
          "\t\t5\t\t7\t\t",
          "\n11\n13\n",  /* LF - line feed */
          "\n\n17\n\n19\n\n",
          "\v23\v29\v",  /* VT - vertical tab */
          "\v\v31\v\v37\v\v",
          "\f41\f43\f",  /* FF - form feed */
          "\f\f47\f\f53\f\f",
          "\r59\r61\r",  /* CR - carrage return */
          "\r\r67\r\r71\r\r"
        };

        for (int i=0; i<10; ++i) {
          x = 0; y = 0;
          sscanf(buffer[i], " %d %d ", &x, &y);
          printf("%d, %d, ",  x, y);
        }

        return 0;
      }
    '''
    self.do_run(src, '''2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, ''')

  def test_sscanf_3(self):
    # i64
    if not Settings.USE_TYPED_ARRAYS == 2: return self.skip('64-bit sscanf only supported in ta2')
    src = r'''
      #include <stdint.h>
      #include <stdio.h>

      int main(){

          int64_t s, m, l;
          printf("%d\n", sscanf("123 1073741823 1125899906842620", "%lld %lld %lld", &s, &m, &l));
          printf("%lld,%lld,%lld\n", s, m, l);

          int64_t negS, negM, negL;
          printf("%d\n", sscanf("-123 -1073741823 -1125899906842620", "%lld %lld %lld", &negS, &negM, &negL));
          printf("%lld,%lld,%lld\n", negS, negM, negL);

          return 0;
      }
    '''

    self.do_run(src, '3\n123,1073741823,1125899906842620\n' +
                   '3\n-123,-1073741823,-1125899906842620\n')

  def test_sscanf_4(self):
    src = r'''
      #include <stdio.h>

      int main()
      {
        char pYear[16], pMonth[16], pDay[16], pDate[64];
        printf("%d\n", sscanf("Nov 19 2012", "%s%s%s", pMonth, pDay, pYear));
        printf("day %s, month %s, year %s \n", pDay, pMonth, pYear);
        return(0);
      }
    '''
    self.do_run(src, '3\nday 19, month Nov, year 2012');

  def test_sscanf_5(self):
    src = r'''
      #include "stdio.h"

      static const char *colors[] = {
        "  c black",
        ". c #001100",
        "X c #111100"
      };

      int main(){
        unsigned char code;
        char color[32];
        int rcode;
        for(int i = 0; i < 3; i++) {
          rcode = sscanf(colors[i], "%c c %s", &code, color);
          printf("%i, %c, %s\n", rcode, code, color);
        }
      }
    '''
    self.do_run(src, '2,  , black\n2, ., #001100\n2, X, #111100');

  def test_sscanf_6(self):
    src = r'''
      #include <stdio.h>
      #include <string.h>
      int main()
      {
        char *date = "18.07.2013w";
        char c[10];
        memset(c, 0, 10);
        int y, m, d, i;
        i = sscanf(date, "%d.%d.%4d%c", &d, &m, &y, c);
        printf("date: %s; day %2d, month %2d, year %4d, extra: %c, %d\n", date, d, m, y, c[0], i);
        i = sscanf(date, "%d.%d.%3c", &d, &m, c);
        printf("date: %s; day %2d, month %2d, year %4d, extra: %s, %d\n", date, d, m, y, c, i);
      }
    '''
    self.do_run(src, '''date: 18.07.2013w; day 18, month  7, year 2013, extra: w, 4
date: 18.07.2013w; day 18, month  7, year 2013, extra: 201, 3
''');

  def test_sscanf_skip(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip("need ta2 for full i64")

    src = r'''
      #include <stdint.h>
      #include <stdio.h>

      int main(){
          int val1;
          printf("%d\n", sscanf("10 20 30 40", "%*lld %*d %d", &val1));
          printf("%d\n", val1);

          int64_t large, val2;
          printf("%d\n", sscanf("1000000 -1125899906842620 -123 -1073741823", "%lld %*lld %ld %*d", &large, &val2));
          printf("%lld,%d\n", large, val2);

          return 0;
      }
    '''
    self.do_run(src, '1\n30\n2\n1000000,-123\n')

  def test_sscanf_caps(self):
    src = r'''
      #include "stdio.h"

      int main(){
        unsigned int a;
        float e, f, g;
        sscanf("a 1.1 1.1 1.1", "%X %E %F %G", &a, &e, &f, &g);
        printf("%d %.1F %.1F %.1F\n", a, e, f, g);
      }
    '''
    self.do_run(src, '10 1.1 1.1 1.1');

  def test_sscanf_hex(self):
    src = r'''
      #include "stdio.h"

      int main(){
        unsigned int a, b;
        sscanf("0x12AB 12AB", "%x %x", &a, &b);
        printf("%d %d\n", a, b);
      }
    '''
    self.do_run(src, '4779 4779')

  def test_sscanf_float(self):
    src = r'''
      #include "stdio.h"

      int main(){
        float f1, f2, f3, f4, f5, f6, f7, f8, f9;
        sscanf("0.512 0.250x5.129_-9.98 1.12*+54.32E3 +54.32E3^87.5E-3 87.5E-3$", "%f %fx%f_%f %f*%f %f^%f %f$", &f1, &f2, &f3, &f4, &f5, &f6, &f7, &f8, &f9);
        printf("\n%f, %f, %f, %f, %f, %f, %f, %f, %f\n", f1, f2, f3, f4, f5, f6, f7, f8, f9);
      }
    '''
    self.do_run(src, '\n0.512000, 0.250000, 5.129000, -9.980000, 1.120000, 54320.000000, 54320.000000, 0.087500, 0.087500\n')

  def test_langinfo(self):
    src = open(path_from_root('tests', 'langinfo', 'test.c'), 'r').read()
    expected = open(path_from_root('tests', 'langinfo', 'output.txt'), 'r').read()
    self.do_run(src, expected, extra_emscripten_args=['-H', 'libc/langinfo.h'])

  def test_files(self):
    self.banned_js_engines = [SPIDERMONKEY_ENGINE] # closure can generate variables called 'gc', which pick up js shell stuff
    if self.emcc_args is not None and '-O2' in self.emcc_args:
      self.emcc_args += ['--closure', '1'] # Use closure here, to test we don't break FS stuff
      self.emcc_args = filter(lambda x: x != '-g', self.emcc_args) # ensure we test --closure 1 --memory-init-file 1 (-g would disable closure)
      self.emcc_args += ["-s", "CHECK_HEAP_ALIGN=0"] # disable heap align check here, it mixes poorly with closure

    Settings.CORRECT_SIGNS = 1 # Just so our output is what we expect. Can flip them both.
    post = '''
def process(filename):
  src = \'\'\'
    var Module = {
      'noFSInit': true,
      'preRun': function() {
        FS.createLazyFile('/', 'test.file', 'test.file', true, false);
        // Test FS_* exporting
        Module['FS_createDataFile']('/', 'somefile.binary', [100, 200, 50, 25, 10, 77, 123], true, false);  // 200 becomes -56, since signed chars are used in memory
        var test_files_input = 'hi there!';
        var test_files_input_index = 0;
        FS.init(function() {
          return test_files_input.charCodeAt(test_files_input_index++) || null;
        });
      }
    };
  \'\'\' + open(filename, 'r').read()
  open(filename, 'w').write(src)
'''
    other = open(os.path.join(self.get_dir(), 'test.file'), 'w')
    other.write('some data');
    other.close()

    src = open(path_from_root('tests', 'files.cpp'), 'r').read()

    mem_file = 'src.cpp.o.js.mem'
    try_delete(mem_file)
    self.do_run(src, ('size: 7\ndata: 100,-56,50,25,10,77,123\nloop: 100 -56 50 25 10 77 123 \ninput:hi there!\ntexto\n$\n5 : 10,30,20,11,88\nother=some data.\nseeked=me da.\nseeked=ata.\nseeked=ta.\nfscanfed: 10 - hello\nok.\ntexte\n', 'size: 7\ndata: 100,-56,50,25,10,77,123\nloop: 100 -56 50 25 10 77 123 \ninput:hi there!\ntexto\ntexte\n$\n5 : 10,30,20,11,88\nother=some data.\nseeked=me da.\nseeked=ata.\nseeked=ta.\nfscanfed: 10 - hello\nok.\n'),
                 post_build=post, extra_emscripten_args=['-H', 'libc/fcntl.h'])
    if self.emcc_args and '--memory-init-file' in self.emcc_args:
      assert os.path.exists(mem_file)

  def test_files_m(self):
    # Test for Module.stdin etc.

    Settings.CORRECT_SIGNS = 1

    post = '''
def process(filename):
  src = \'\'\'
    var data = [10, 20, 40, 30];
    var Module = {
      stdin: function() { return data.pop() || null },
      stdout: function(x) { Module.print('got: ' + x) }
    };
  \'\'\' + open(filename, 'r').read()
  open(filename, 'w').write(src)
'''
    src = r'''
      #include <stdio.h>
      #include <unistd.h>

      int main () {
        char c;
        fprintf(stderr, "isatty? %d,%d,%d\n", isatty(fileno(stdin)), isatty(fileno(stdout)), isatty(fileno(stderr)));
        while ((c = fgetc(stdin)) != EOF) {
          putc(c+5, stdout);
        }
        return 0;
      }
      '''
    self.do_run(src, ('got: 35\ngot: 45\ngot: 25\ngot: 15\nisatty? 0,0,1\n', 'isatty? 0,0,1\ngot: 35\ngot: 45\ngot: 25\ngot: 15\n'), post_build=post)

  def test_fwrite_0(self):
    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      int main ()
      {
          FILE *fh;

          fh = fopen("a.txt", "wb");
          if (!fh) exit(1);
          fclose(fh);

          fh = fopen("a.txt", "rb");
          if (!fh) exit(1);

          char data[] = "foobar";
          size_t written = fwrite(data, 1, sizeof(data), fh);

          printf("written=%zu\n", written);
      }
      '''
    self.do_run(src, 'written=0')

  def test_fgetc_ungetc(self):
    src = open(path_from_root('tests', 'stdio', 'test_fgetc_ungetc.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_fgetc_unsigned(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    src = r'''
      #include <stdio.h>
      int main() {
        FILE *file = fopen("file_with_byte_234.txt", "rb");
        int c = fgetc(file);
        printf("*%d\n", c);
      }
    '''
    open('file_with_byte_234.txt', 'wb').write('\xea')
    self.emcc_args += ['--embed-file', 'file_with_byte_234.txt']
    self.do_run(src, '*234\n')

  def test_fgets_eol(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    src = r'''
      #include <stdio.h>
      char buf[32];
      int main()
      {
        char *r = "SUCCESS";
        FILE *f = fopen("eol.txt", "r");
        while (fgets(buf, 32, f) != NULL) {
          if (buf[0] == '\0') {
            r = "FAIL";
            break;
          }
        }
        printf("%s\n", r);
        fclose(f);
        return 0;
      }
    '''
    open('eol.txt', 'wb').write('\n')
    self.emcc_args += ['--embed-file', 'eol.txt']
    self.do_run(src, 'SUCCESS\n')

  def test_fscanf(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    open(os.path.join(self.get_dir(), 'three_numbers.txt'), 'w').write('''-1 0.1 -.1''')
    src = r'''
      #include <stdio.h>
      #include <assert.h>
      #include <float.h>
      int main()
      {
          float x = FLT_MAX, y = FLT_MAX, z = FLT_MAX;

          FILE* fp = fopen("three_numbers.txt", "r");
          if (fp) {
              int match = fscanf(fp, " %f %f %f ", &x, &y, &z);
              printf("match = %d\n", match);
              printf("x = %0.1f, y = %0.1f, z = %0.1f\n", x, y, z);
          } else {
              printf("failed to open three_numbers.txt\n");
          }
          return 0;
      }
    '''
    self.emcc_args += ['--embed-file', 'three_numbers.txt']
    self.do_run(src, 'match = 3\nx = -1.0, y = 0.1, z = -0.1\n')

  def test_readdir(self):
    src = open(path_from_root('tests', 'dirent', 'test_readdir.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_stat(self):
    src = open(path_from_root('tests', 'stat', 'test_stat.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_stat_chmod(self):
    src = open(path_from_root('tests', 'stat', 'test_chmod.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_stat_mknod(self):
    src = open(path_from_root('tests', 'stat', 'test_mknod.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_fcntl(self):
    add_pre_run = '''
def process(filename):
  src = open(filename, 'r').read().replace(
    '// {{PRE_RUN_ADDITIONS}}',
    "FS.createDataFile('/', 'test', 'abcdef', true, true);"
  )
  open(filename, 'w').write(src)
'''
    src = open(path_from_root('tests', 'fcntl', 'src.c'), 'r').read()
    expected = open(path_from_root('tests', 'fcntl', 'output.txt'), 'r').read()
    self.do_run(src, expected, post_build=add_pre_run, extra_emscripten_args=['-H', 'libc/fcntl.h'])

  def test_fcntl_open(self):
    src = open(path_from_root('tests', 'fcntl-open', 'src.c'), 'r').read()
    expected = open(path_from_root('tests', 'fcntl-open', 'output.txt'), 'r').read()
    self.do_run(src, expected, force_c=True, extra_emscripten_args=['-H', 'libc/fcntl.h'])

  def test_fcntl_misc(self):
    add_pre_run = '''
def process(filename):
  src = open(filename, 'r').read().replace(
    '// {{PRE_RUN_ADDITIONS}}',
    "FS.createDataFile('/', 'test', 'abcdef', true, true);"
  )
  open(filename, 'w').write(src)
'''
    src = open(path_from_root('tests', 'fcntl-misc', 'src.c'), 'r').read()
    expected = open(path_from_root('tests', 'fcntl-misc', 'output.txt'), 'r').read()
    self.do_run(src, expected, post_build=add_pre_run, extra_emscripten_args=['-H', 'libc/fcntl.h'])

  def test_poll(self):
    add_pre_run = '''
def process(filename):
  src = open(filename, 'r').read().replace(
    '// {{PRE_RUN_ADDITIONS}}',
    \'\'\'
      var dummy_device = FS.makedev(64, 0);
      FS.registerDevice(dummy_device, {});

      FS.createDataFile('/', 'file', 'abcdef', true, true);
      FS.mkdev('/device', dummy_device);
    \'\'\'
  )
  open(filename, 'w').write(src)
'''
    src = r'''
      #include <stdio.h>
      #include <errno.h>
      #include <fcntl.h>
      #include <poll.h>

      int main() {
        struct pollfd multi[5];
        multi[0].fd = open("/file", O_RDONLY, 0777);
        multi[1].fd = open("/device", O_RDONLY, 0777);
        multi[2].fd = 123;
        multi[3].fd = open("/file", O_RDONLY, 0777);
        multi[4].fd = open("/file", O_RDONLY, 0777);
        multi[0].events = POLLIN | POLLOUT | POLLNVAL | POLLERR;
        multi[1].events = POLLIN | POLLOUT | POLLNVAL | POLLERR;
        multi[2].events = POLLIN | POLLOUT | POLLNVAL | POLLERR;
        multi[3].events = 0x00;
        multi[4].events = POLLOUT | POLLNVAL | POLLERR;

        printf("ret: %d\n", poll(multi, 5, 123));
        printf("errno: %d\n", errno);
        printf("multi[0].revents: %d\n", multi[0].revents == (POLLIN | POLLOUT));
        printf("multi[1].revents: %d\n", multi[1].revents == (POLLIN | POLLOUT));
        printf("multi[2].revents: %d\n", multi[2].revents == POLLNVAL);
        printf("multi[3].revents: %d\n", multi[3].revents == 0);
        printf("multi[4].revents: %d\n", multi[4].revents == POLLOUT);

        return 0;
      }
      '''
    expected = r'''
      ret: 4
      errno: 0
      multi[0].revents: 1
      multi[1].revents: 1
      multi[2].revents: 1
      multi[3].revents: 1
      multi[4].revents: 1
      '''
    self.do_run(src, re.sub('(^|\n)\s+', '\\1', expected), post_build=add_pre_run, extra_emscripten_args=['-H', 'libc/fcntl.h,poll.h'])

  def test_statvfs(self):
    src = r'''
      #include <stdio.h>
      #include <errno.h>
      #include <sys/statvfs.h>

      int main() {
        struct statvfs s;

        printf("result: %d\n", statvfs("/test", &s));
        printf("errno: %d\n", errno);

        printf("f_bsize: %lu\n", s.f_bsize);
        printf("f_frsize: %lu\n", s.f_frsize);
        printf("f_blocks: %lu\n", s.f_blocks);
        printf("f_bfree: %lu\n", s.f_bfree);
        printf("f_bavail: %lu\n", s.f_bavail);
        printf("f_files: %d\n", s.f_files > 5);
        printf("f_ffree: %lu\n", s.f_ffree);
        printf("f_favail: %lu\n", s.f_favail);
        printf("f_fsid: %lu\n", s.f_fsid);
        printf("f_flag: %lu\n", s.f_flag);
        printf("f_namemax: %lu\n", s.f_namemax);

        return 0;
      }
      '''
    expected = r'''
      result: 0
      errno: 0
      f_bsize: 4096
      f_frsize: 4096
      f_blocks: 1000000
      f_bfree: 500000
      f_bavail: 500000
      f_files: 1
      f_ffree: 1000000
      f_favail: 1000000
      f_fsid: 42
      f_flag: 2
      f_namemax: 255
      '''
    self.do_run(src, re.sub('(^|\n)\s+', '\\1', expected))

  def test_libgen(self):
    src = r'''
      #include <stdio.h>
      #include <libgen.h>

      int main() {
        char p1[16] = "/usr/lib", p1x[16] = "/usr/lib";
        printf("%s -> ", p1);
        printf("%s : %s\n", dirname(p1x), basename(p1));

        char p2[16] = "/usr", p2x[16] = "/usr";
        printf("%s -> ", p2);
        printf("%s : %s\n", dirname(p2x), basename(p2));

        char p3[16] = "/usr/", p3x[16] = "/usr/";
        printf("%s -> ", p3);
        printf("%s : %s\n", dirname(p3x), basename(p3));

        char p4[16] = "/usr/lib///", p4x[16] = "/usr/lib///";
        printf("%s -> ", p4);
        printf("%s : %s\n", dirname(p4x), basename(p4));

        char p5[16] = "/", p5x[16] = "/";
        printf("%s -> ", p5);
        printf("%s : %s\n", dirname(p5x), basename(p5));

        char p6[16] = "///", p6x[16] = "///";
        printf("%s -> ", p6);
        printf("%s : %s\n", dirname(p6x), basename(p6));

        char p7[16] = "/usr/../lib/..", p7x[16] = "/usr/../lib/..";
        printf("%s -> ", p7);
        printf("%s : %s\n", dirname(p7x), basename(p7));

        char p8[16] = "", p8x[16] = "";
        printf("(empty) -> %s : %s\n", dirname(p8x), basename(p8));

        printf("(null) -> %s : %s\n", dirname(0), basename(0));

        return 0;
      }
      '''
    expected = '''
      /usr/lib -> /usr : lib
      /usr -> / : usr
      /usr/ -> / : usr
      /usr/lib/// -> /usr : lib
      / -> / : /
      /// -> / : /
      /usr/../lib/.. -> /usr/../lib : ..
      (empty) -> . : .
      (null) -> . : .
    '''
    self.do_run(src, re.sub('(^|\n)\s+', '\\1', expected))

  def test_utime(self):
    src = open(path_from_root('tests', 'utime', 'test_utime.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_utf(self):
    self.banned_js_engines = [SPIDERMONKEY_ENGINE] # only node handles utf well
    Settings.EXPORTED_FUNCTIONS = ['_main', '_malloc']

    src = r'''
      #include <stdio.h>
      #include <emscripten.h>

      int main() {
        char *c = "μ†ℱ ╋ℯ╳╋ 😇";
        printf("%d %d %d %d %s\n", c[0]&0xff, c[1]&0xff, c[2]&0xff, c[3]&0xff, c);
        emscripten_run_script(
          "cheez = _malloc(100);"
          "Module.writeStringToMemory(\"μ†ℱ ╋ℯ╳╋ 😇\", cheez);"
          "Module.print([Pointer_stringify(cheez), Module.getValue(cheez, 'i8')&0xff, Module.getValue(cheez+1, 'i8')&0xff, Module.getValue(cheez+2, 'i8')&0xff, Module.getValue(cheez+3, 'i8')&0xff, ]);");
      }
    '''
    self.do_run(src, '206 188 226 128 μ†ℱ ╋ℯ╳╋ 😇\nμ†ℱ ╋ℯ╳╋ 😇,206,188,226,128\n');

  def test_utf32(self):
    if self.emcc_args is None: return self.skip('need libc for wcslen()')
    if not self.is_le32(): return self.skip('this test uses inline js, which requires le32')
    self.do_run(open(path_from_root('tests', 'utf32.cpp')).read(), 'OK.')
    self.do_run(open(path_from_root('tests', 'utf32.cpp')).read(), 'OK.', args=['-fshort-wchar'])

  def test_direct_string_constant_usage(self):
    if self.emcc_args is None: return self.skip('requires libcxx')

    src = '''
      #include <iostream>
      template<int i>
      void printText( const char (&text)[ i ] )
      {
         std::cout << text;
      }
      int main()
      {
        printText( "some string constant" );
        return 0;
      }
    '''
    self.do_run(src, "some string constant")

  def test_std_cout_new(self):
    if self.emcc_args is None: return self.skip('requires emcc')

    src = '''
      #include <iostream>

      struct NodeInfo { //structure that we want to transmit to our shaders
          float x;
          float y;
          float s;
          float c;
      };
      const int nbNodes = 100;
      NodeInfo * data = new NodeInfo[nbNodes]; //our data that will be transmitted using float texture.

      template<int i>
      void printText( const char (&text)[ i ] )
      {
         std::cout << text << std::endl;
      }

      int main()
      {
        printText( "some string constant" );
        return 0;
      }
    '''

    self.do_run(src, "some string constant")

  def test_istream(self):
    if self.emcc_args is None: return self.skip('requires libcxx')

    src = '''
      #include <string>
      #include <sstream>
      #include <iostream>

      int main()
      {
          std::string mystring("1 2 3");
          std::istringstream is(mystring);
          int one, two, three;

          is >> one >> two >> three;

          printf( "%i %i %i", one, two, three );
      }
    '''
    for linkable in [0]:#, 1]:
      print linkable
      Settings.LINKABLE = linkable # regression check for issue #273
      self.do_run(src, "1 2 3")

  def test_fs_base(self):
    Settings.INCLUDE_FULL_LIBRARY = 1
    try:
      addJS = '''
def process(filename):
  import tools.shared as shared
  src = open(filename, 'r').read().replace('FS.init();', '').replace( # Disable normal initialization, replace with ours
    '// {{PRE_RUN_ADDITIONS}}',
    open(shared.path_from_root('tests', 'filesystem', 'src.js'), 'r').read())
  open(filename, 'w').write(src)
'''
      src = 'int main() {return 0;}\n'
      expected = open(path_from_root('tests', 'filesystem', 'output.txt'), 'r').read()
      self.do_run(src, expected, post_build=addJS, extra_emscripten_args=['-H', 'libc/fcntl.h,libc/sys/unistd.h,poll.h,libc/math.h,libc/langinfo.h,libc/time.h'])
    finally:
      Settings.INCLUDE_FULL_LIBRARY = 0

  def test_fs_nodefs_rw(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    if not self.is_le32(): return self.skip('le32 needed for inline js')
    src = open(path_from_root('tests', 'fs', 'test_nodefs_rw.c'), 'r').read()
    self.do_run(src, 'success', force_c=True, js_engines=[NODE_JS])

  def test_unistd_access(self):
    self.clear()
    if not self.is_le32(): return self.skip('le32 needed for inline js')
    for fs in ['MEMFS', 'NODEFS']:
      src = open(path_from_root('tests', 'unistd', 'access.c'), 'r').read()
      expected = open(path_from_root('tests', 'unistd', 'access.out'), 'r').read()
      Building.COMPILER_TEST_OPTS += ['-D' + fs]
      self.do_run(src, expected, js_engines=[NODE_JS])

  def test_unistd_curdir(self):
    if not self.is_le32(): return self.skip('le32 needed for inline js')
    src = open(path_from_root('tests', 'unistd', 'curdir.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'curdir.out'), 'r').read()
    self.do_run(src, expected)

  def test_unistd_close(self):
    src = open(path_from_root('tests', 'unistd', 'close.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'close.out'), 'r').read()
    self.do_run(src, expected)

  def test_unistd_confstr(self):
    src = open(path_from_root('tests', 'unistd', 'confstr.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'confstr.out'), 'r').read()
    self.do_run(src, expected, extra_emscripten_args=['-H', 'libc/unistd.h'])

  def test_unistd_ttyname(self):
    src = open(path_from_root('tests', 'unistd', 'ttyname.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_unistd_dup(self):
    src = open(path_from_root('tests', 'unistd', 'dup.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'dup.out'), 'r').read()
    self.do_run(src, expected)

  def test_unistd_pathconf(self):
    src = open(path_from_root('tests', 'unistd', 'pathconf.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'pathconf.out'), 'r').read()
    self.do_run(src, expected)

  def test_unistd_truncate(self):
    self.clear()
    if not self.is_le32(): return self.skip('le32 needed for inline js')
    for fs in ['MEMFS', 'NODEFS']:
      src = open(path_from_root('tests', 'unistd', 'truncate.c'), 'r').read()
      expected = open(path_from_root('tests', 'unistd', 'truncate.out'), 'r').read()
      Building.COMPILER_TEST_OPTS += ['-D' + fs]
      self.do_run(src, expected, js_engines=[NODE_JS])

  def test_unistd_swab(self):
    src = open(path_from_root('tests', 'unistd', 'swab.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'swab.out'), 'r').read()
    self.do_run(src, expected)

  def test_unistd_isatty(self):
    src = open(path_from_root('tests', 'unistd', 'isatty.c'), 'r').read()
    self.do_run(src, 'success', force_c=True)

  def test_unistd_sysconf(self):
    src = open(path_from_root('tests', 'unistd', 'sysconf.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'sysconf.out'), 'r').read()
    self.do_run(src, expected)

  def test_unistd_login(self):
    src = open(path_from_root('tests', 'unistd', 'login.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'login.out'), 'r').read()
    self.do_run(src, expected)

  def test_unistd_unlink(self):
    self.clear()
    if self.emcc_args is None: return self.skip('requires emcc')
    if not self.is_le32(): return self.skip('le32 needed for inline js')
    for fs in ['MEMFS', 'NODEFS']:
      src = open(path_from_root('tests', 'unistd', 'unlink.c'), 'r').read()
      Building.COMPILER_TEST_OPTS += ['-D' + fs]
      self.do_run(src, 'success', force_c=True, js_engines=[NODE_JS])

  def test_unistd_links(self):
    self.clear()
    if not self.is_le32(): return self.skip('le32 needed for inline js')
    for fs in ['MEMFS', 'NODEFS']:
      if WINDOWS and fs == 'NODEFS':
        print >> sys.stderr, 'Skipping NODEFS part of this test for test_unistd_links on Windows, since it would require administrative privileges.'
        # Also, other detected discrepancies if you do end up running this test on NODEFS:
        # test expects /, but Windows gives \ as path slashes.
        # Calling readlink() on a non-link gives error 22 EINVAL on Unix, but simply error 0 OK on Windows.
        continue
      src = open(path_from_root('tests', 'unistd', 'links.c'), 'r').read()
      expected = open(path_from_root('tests', 'unistd', 'links.out'), 'r').read()
      Building.COMPILER_TEST_OPTS += ['-D' + fs]
      self.do_run(src, expected, js_engines=[NODE_JS])

  def test_unistd_sleep(self):
    src = open(path_from_root('tests', 'unistd', 'sleep.c'), 'r').read()
    expected = open(path_from_root('tests', 'unistd', 'sleep.out'), 'r').read()
    self.do_run(src, expected)

  def test_unistd_io(self):
    self.clear()
    if not self.is_le32(): return self.skip('le32 needed for inline js')
    if self.run_name == 'o2': return self.skip('non-asm optimized builds can fail with inline js')
    if self.emcc_args is None: return self.skip('requires emcc')
    for fs in ['MEMFS', 'NODEFS']:
      src = open(path_from_root('tests', 'unistd', 'io.c'), 'r').read()
      expected = open(path_from_root('tests', 'unistd', 'io.out'), 'r').read()
      Building.COMPILER_TEST_OPTS += ['-D' + fs]
      self.do_run(src, expected, js_engines=[NODE_JS])

  def test_unistd_misc(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    if not self.is_le32(): return self.skip('le32 needed for inline js')
    for fs in ['MEMFS', 'NODEFS']:
      src = open(path_from_root('tests', 'unistd', 'misc.c'), 'r').read()
      expected = open(path_from_root('tests', 'unistd', 'misc.out'), 'r').read()
      Building.COMPILER_TEST_OPTS += ['-D' + fs]
      self.do_run(src, expected, js_engines=[NODE_JS])

  def test_uname(self):
    src = r'''
      #include <stdio.h>
      #include <sys/utsname.h>

      int main() {
        struct utsname u;
        printf("ret: %d\n", uname(&u));
        printf("sysname: %s\n", u.sysname);
        printf("nodename: %s\n", u.nodename);
        printf("release: %s\n", u.release);
        printf("version: %s\n", u.version);
        printf("machine: %s\n", u.machine);
        printf("invalid: %d\n", uname(0));
        return 0;
      }
      '''
    expected = '''
      ret: 0
      sysname: Emscripten
      nodename: emscripten
      release: 1.0
      version: #1
      machine: x86-JS
    '''
    self.do_run(src, re.sub('(^|\n)\s+', '\\1', expected))

  def test_env(self):
    src = open(path_from_root('tests', 'env', 'src.c'), 'r').read()
    expected = open(path_from_root('tests', 'env', 'output.txt'), 'r').read()
    self.do_run(src, expected)

  def test_systypes(self):
    src = open(path_from_root('tests', 'systypes', 'src.c'), 'r').read()
    expected = open(path_from_root('tests', 'systypes', 'output.txt'), 'r').read()
    self.do_run(src, expected)

  def test_getloadavg(self):
    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      int main() {
        double load[5] = {42.13, 42.13, 42.13, 42.13, 42.13};
        printf("ret: %d\n", getloadavg(load, 5));
        printf("load[0]: %.3lf\n", load[0]);
        printf("load[1]: %.3lf\n", load[1]);
        printf("load[2]: %.3lf\n", load[2]);
        printf("load[3]: %.3lf\n", load[3]);
        printf("load[4]: %.3lf\n", load[4]);
        return 0;
      }
      '''
    expected = '''
      ret: 3
      load[0]: 0.100
      load[1]: 0.100
      load[2]: 0.100
      load[3]: 42.130
      load[4]: 42.130
    '''
    self.do_run(src, re.sub('(^|\n)\s+', '\\1', expected))

  def test_799(self):
    src = open(path_from_root('tests', '799.cpp'), 'r').read()
    self.do_run(src, '''Set PORT family: 0, port: 3979
Get PORT family: 0
PORT: 3979
''')

  def test_ctype(self):
    # The bit fiddling done by the macros using __ctype_b_loc requires this.
    Settings.CORRECT_SIGNS = 1
    src = open(path_from_root('tests', 'ctype', 'src.c'), 'r').read()
    expected = open(path_from_root('tests', 'ctype', 'output.txt'), 'r').read()
    self.do_run(src, expected)

  def test_strcasecmp(self):
    src = r'''
      #include <stdio.h>
      #include <strings.h>
      int sign(int x) {
        if (x < 0) return -1;
        if (x > 0) return 1;
        return 0;
      }
      int main() {
        printf("*\n");

        printf("%d\n", sign(strcasecmp("hello", "hello")));
        printf("%d\n", sign(strcasecmp("hello1", "hello")));
        printf("%d\n", sign(strcasecmp("hello", "hello1")));
        printf("%d\n", sign(strcasecmp("hello1", "hello1")));
        printf("%d\n", sign(strcasecmp("iello", "hello")));
        printf("%d\n", sign(strcasecmp("hello", "iello")));
        printf("%d\n", sign(strcasecmp("A", "hello")));
        printf("%d\n", sign(strcasecmp("Z", "hello")));
        printf("%d\n", sign(strcasecmp("a", "hello")));
        printf("%d\n", sign(strcasecmp("z", "hello")));
        printf("%d\n", sign(strcasecmp("hello", "a")));
        printf("%d\n", sign(strcasecmp("hello", "z")));

        printf("%d\n", sign(strcasecmp("Hello", "hello")));
        printf("%d\n", sign(strcasecmp("Hello1", "hello")));
        printf("%d\n", sign(strcasecmp("Hello", "hello1")));
        printf("%d\n", sign(strcasecmp("Hello1", "hello1")));
        printf("%d\n", sign(strcasecmp("Iello", "hello")));
        printf("%d\n", sign(strcasecmp("Hello", "iello")));
        printf("%d\n", sign(strcasecmp("A", "hello")));
        printf("%d\n", sign(strcasecmp("Z", "hello")));
        printf("%d\n", sign(strcasecmp("a", "hello")));
        printf("%d\n", sign(strcasecmp("z", "hello")));
        printf("%d\n", sign(strcasecmp("Hello", "a")));
        printf("%d\n", sign(strcasecmp("Hello", "z")));

        printf("%d\n", sign(strcasecmp("hello", "Hello")));
        printf("%d\n", sign(strcasecmp("hello1", "Hello")));
        printf("%d\n", sign(strcasecmp("hello", "Hello1")));
        printf("%d\n", sign(strcasecmp("hello1", "Hello1")));
        printf("%d\n", sign(strcasecmp("iello", "Hello")));
        printf("%d\n", sign(strcasecmp("hello", "Iello")));
        printf("%d\n", sign(strcasecmp("A", "Hello")));
        printf("%d\n", sign(strcasecmp("Z", "Hello")));
        printf("%d\n", sign(strcasecmp("a", "Hello")));
        printf("%d\n", sign(strcasecmp("z", "Hello")));
        printf("%d\n", sign(strcasecmp("hello", "a")));
        printf("%d\n", sign(strcasecmp("hello", "z")));

        printf("%d\n", sign(strcasecmp("Hello", "Hello")));
        printf("%d\n", sign(strcasecmp("Hello1", "Hello")));
        printf("%d\n", sign(strcasecmp("Hello", "Hello1")));
        printf("%d\n", sign(strcasecmp("Hello1", "Hello1")));
        printf("%d\n", sign(strcasecmp("Iello", "Hello")));
        printf("%d\n", sign(strcasecmp("Hello", "Iello")));
        printf("%d\n", sign(strcasecmp("A", "Hello")));
        printf("%d\n", sign(strcasecmp("Z", "Hello")));
        printf("%d\n", sign(strcasecmp("a", "Hello")));
        printf("%d\n", sign(strcasecmp("z", "Hello")));
        printf("%d\n", sign(strcasecmp("Hello", "a")));
        printf("%d\n", sign(strcasecmp("Hello", "z")));

        printf("%d\n", sign(strncasecmp("hello", "hello", 3)));
        printf("%d\n", sign(strncasecmp("hello1", "hello", 3)));
        printf("%d\n", sign(strncasecmp("hello", "hello1", 3)));
        printf("%d\n", sign(strncasecmp("hello1", "hello1", 3)));
        printf("%d\n", sign(strncasecmp("iello", "hello", 3)));
        printf("%d\n", sign(strncasecmp("hello", "iello", 3)));
        printf("%d\n", sign(strncasecmp("A", "hello", 3)));
        printf("%d\n", sign(strncasecmp("Z", "hello", 3)));
        printf("%d\n", sign(strncasecmp("a", "hello", 3)));
        printf("%d\n", sign(strncasecmp("z", "hello", 3)));
        printf("%d\n", sign(strncasecmp("hello", "a", 3)));
        printf("%d\n", sign(strncasecmp("hello", "z", 3)));

        printf("*\n");

        return 0;
      }
    '''
    self.do_run(src, '''*\n0\n1\n-1\n0\n1\n-1\n-1\n1\n-1\n1\n1\n-1\n0\n1\n-1\n0\n1\n-1\n-1\n1\n-1\n1\n1\n-1\n0\n1\n-1\n0\n1\n-1\n-1\n1\n-1\n1\n1\n-1\n0\n1\n-1\n0\n1\n-1\n-1\n1\n-1\n1\n1\n-1\n0\n0\n0\n0\n1\n-1\n-1\n1\n-1\n1\n1\n-1\n*\n''')

  def test_atomic(self):
    src = '''
      #include <stdio.h>
      int main() {
        int x = 10;
        int y = __sync_add_and_fetch(&x, 5);
        printf("*%d,%d*\\n", x, y);
        x = 10;
        y = __sync_fetch_and_add(&x, 5);
        printf("*%d,%d*\\n", x, y);
        x = 10;
        y = __sync_lock_test_and_set(&x, 6);
        printf("*%d,%d*\\n", x, y);
        x = 10;
        y = __sync_bool_compare_and_swap(&x, 9, 7);
        printf("*%d,%d*\\n", x, y);
        y = __sync_bool_compare_and_swap(&x, 10, 7);
        printf("*%d,%d*\\n", x, y);
        return 0;
      }
    '''

    self.do_run(src, '*15,15*\n*15,10*\n*6,10*\n*10,0*\n*7,1*')

  def test_phiundef(self):
    src = r'''
#include <stdlib.h>
#include <stdio.h>

static int state;

struct my_struct {
union {
  struct {
    unsigned char a;
    unsigned char b;
  } c;
  unsigned int d;
} e;
unsigned int f;
};

int main(int argc, char **argv) {
  struct my_struct r;

  state = 0;

  for (int i=0;i<argc+10;i++)
  {
      if (state % 2 == 0)
          r.e.c.a = 3;
      else
          printf("%d\n", r.e.c.a);
      state++;
  }
  return 0;
}
    '''

    self.do_run(src, '3\n3\n3\n3\n3\n')

  # libc++ tests

  def test_iostream(self):
    if Settings.QUANTUM_SIZE == 1: return self.skip("we don't support libcxx in q1")
    if self.emcc_args is None: return self.skip('needs ta2 and emcc')

    src = '''
      #include <iostream>

      int main()
      {
        std::cout << "hello world" << std::endl << 77 << "." << std::endl;
        return 0;
      }
    '''

    # FIXME: should not have so many newlines in output here
    self.do_run(src, 'hello world\n77.\n')

  def test_stdvec(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    src = '''
      #include <vector>
      #include <stdio.h>

      struct S {
          int a;
          float b;
      };

      void foo(int a, float b)
      {
        printf("%d:%.2f\\n", a, b);
      }

      int main ( int argc, char *argv[] )
      {
        std::vector<S> ar;
        S s;

        s.a = 789;
        s.b = 123.456f;
        ar.push_back(s);

        s.a = 0;
        s.b = 100.1f;
        ar.push_back(s);

        foo(ar[0].a, ar[0].b);
        foo(ar[1].a, ar[1].b);
      }
    '''

    self.do_run(src, '789:123.46\n0:100.1')

  def test_reinterpreted_ptrs(self):
    if self.emcc_args is None: return self.skip('needs emcc and libc')

    src = r'''
#include <stdio.h>

class Foo {
private:
  float bar;
public:
  int baz;

  Foo(): bar(0), baz(4711) {};

  int getBar() const;
};

int Foo::getBar() const {
  return this->bar;
};

const Foo *magic1 = reinterpret_cast<Foo*>(0xDEAD111F);
const Foo *magic2 = reinterpret_cast<Foo*>(0xDEAD888F);

static void runTest() {

  const Foo *a = new Foo();
  const Foo *b = a;

  if (a->getBar() == 0) {
      if (a->baz == 4712)
          b = magic1;
      else
          b = magic2;
  }

  printf("%s\n", (b == magic1 ? "magic1" : (b == magic2 ? "magic2" : "neither")));
};

extern "C" {
  int main(int argc, char **argv) {
      runTest();
  }
}
'''
    self.do_run(src, 'magic2')

  def test_jansson(self):
      return self.skip('currently broken')

      if Settings.USE_TYPED_ARRAYS != 2: return self.skip('requires ta2')
      if Settings.SAFE_HEAP: return self.skip('jansson is not safe-heap safe')

      src = '''
        #include <jansson.h>
        #include <stdio.h>
        #include <string.h>

        int main()
        {
          const char* jsonString = "{\\"key\\": \\"value\\",\\"array\\": [\\"array_item1\\",\\"array_item2\\",\\"array_item3\\"],\\"dict\\":{\\"number\\": 3,\\"float\\": 2.2}}";

          json_error_t error;
          json_t *root = json_loadb(jsonString, strlen(jsonString), 0, &error);

          if(!root) {
            printf("Node `root` is `null`.");
            return 0;
          }

          if(!json_is_object(root)) {
            printf("Node `root` is no object.");
            return 0;
          }

          printf("%s\\n", json_string_value(json_object_get(root, "key")));

          json_t *array = json_object_get(root, "array");
          if(!array) {
            printf("Node `array` is `null`.");
            return 0;
          }

          if(!json_is_array(array)) {
            printf("Node `array` is no array.");
            return 0;
          }

          for(size_t i=0; i<json_array_size(array); ++i)
          {
            json_t *arrayNode = json_array_get(array, i);
            if(!root || !json_is_string(arrayNode))
              return 0;
            printf("%s\\n", json_string_value(arrayNode));
          }

          json_t *dict = json_object_get(root, "dict");
          if(!dict || !json_is_object(dict))
            return 0;

          json_t *numberNode = json_object_get(dict, "number");
          json_t *floatNode = json_object_get(dict, "float");

          if(!numberNode || !json_is_number(numberNode) ||
             !floatNode || !json_is_real(floatNode))
            return 0;

          printf("%i\\n", json_integer_value(numberNode));
          printf("%.2f\\n", json_number_value(numberNode));
          printf("%.2f\\n", json_real_value(floatNode));

          json_t *invalidNode = json_object_get(dict, "invalidNode");
          if(invalidNode)
            return 0;

          printf("%i\\n", json_number_value(invalidNode));

          json_decref(root);

          if(!json_is_object(root))
            printf("jansson!\\n");

          return 0;
        }
      '''
      self.do_run(src, 'value\narray_item1\narray_item2\narray_item3\n3\n3.00\n2.20\nJansson: Node with ID `0` not found. Context has `10` nodes.\n0\nJansson: No JSON context.\njansson!')

  ### 'Medium' tests

  def test_fannkuch(self):
      results = [ (1,0), (2,1), (3,2), (4,4), (5,7), (6,10), (7, 16), (8,22) ]
      for i, j in results:
        src = open(path_from_root('tests', 'fannkuch.cpp'), 'r').read()
        self.do_run(src, 'Pfannkuchen(%d) = %d.' % (i,j), [str(i)], no_build=i>1)

  def test_raytrace(self):
      if self.emcc_args is None: return self.skip('requires emcc')
      if Settings.USE_TYPED_ARRAYS == 2: return self.skip('Relies on double value rounding, extremely sensitive')

      src = open(path_from_root('tests', 'raytrace.cpp'), 'r').read().replace('double', 'float')
      output = open(path_from_root('tests', 'raytrace.ppm'), 'r').read()
      self.do_run(src, output, ['3', '16'])#, build_ll_hook=self.do_autodebug)

  def test_fasta(self):
      if self.emcc_args is None: return self.skip('requires emcc')
      results = [ (1,'''GG*ctt**tgagc*'''), (20,'''GGCCGGGCGCGGTGGCTCACGCCTGTAATCCCAGCACTTT*cttBtatcatatgctaKggNcataaaSatgtaaaDcDRtBggDtctttataattcBgtcg**tacgtgtagcctagtgtttgtgttgcgttatagtctatttgtggacacagtatggtcaaa**tgacgtcttttgatctgacggcgttaacaaagatactctg*'''),
(50,'''GGCCGGGCGCGGTGGCTCACGCCTGTAATCCCAGCACTTTGGGAGGCCGAGGCGGGCGGA*TCACCTGAGGTCAGGAGTTCGAGACCAGCCTGGCCAACAT*cttBtatcatatgctaKggNcataaaSatgtaaaDcDRtBggDtctttataattcBgtcg**tactDtDagcctatttSVHtHttKtgtHMaSattgWaHKHttttagacatWatgtRgaaa**NtactMcSMtYtcMgRtacttctWBacgaa**agatactctgggcaacacacatacttctctcatgttgtttcttcggacctttcataacct**ttcctggcacatggttagctgcacatcacaggattgtaagggtctagtggttcagtgagc**ggaatatcattcgtcggtggtgttaatctatctcggtgtagcttataaatgcatccgtaa**gaatattatgtttatttgtcggtacgttcatggtagtggtgtcgccgatttagacgtaaa**ggcatgtatg*''') ]
      for precision in [0, 1, 2]:
        Settings.PRECISE_F32 = precision
        for t in ['float', 'double']:
          print precision, t
          src = open(path_from_root('tests', 'fasta.cpp'), 'r').read().replace('double', t)
          for i, j in results:
            self.do_run(src, j, [str(i)], lambda x, err: x.replace('\n', '*'), no_build=i>1)
          shutil.copyfile('src.cpp.o.js', '%d_%s.js' % (precision, t))

  def test_whets(self):
    if not Settings.ASM_JS: return self.skip('mainly a test for asm validation here')
    self.do_run(open(path_from_root('tests', 'whets.cpp')).read(), 'Single Precision C Whetstone Benchmark')

  def test_dlmalloc(self):
    if self.emcc_args is None: self.emcc_args = [] # dlmalloc auto-inclusion is only done if we use emcc

    self.banned_js_engines = [NODE_JS] # slower, and fail on 64-bit
    Settings.CORRECT_SIGNS = 2
    Settings.CORRECT_SIGNS_LINES = ['src.cpp:' + str(i+4) for i in [4816, 4191, 4246, 4199, 4205, 4235, 4227]]
    Settings.TOTAL_MEMORY = 128*1024*1024 # needed with typed arrays

    src = open(path_from_root('system', 'lib', 'dlmalloc.c'), 'r').read() + '\n\n\n' + open(path_from_root('tests', 'dlmalloc_test.c'), 'r').read()
    self.do_run(src, '*1,0*', ['200', '1'])
    self.do_run(src, '*400,0*', ['400', '400'], no_build=True)

    # Linked version
    src = open(path_from_root('tests', 'dlmalloc_test.c'), 'r').read()
    self.do_run(src, '*1,0*', ['200', '1'], extra_emscripten_args=['-m'])
    self.do_run(src, '*400,0*', ['400', '400'], extra_emscripten_args=['-m'], no_build=True)

    if self.emcc_args == []: # TODO: do this in other passes too, passing their opts into emcc
      # emcc should build in dlmalloc automatically, and do all the sign correction etc. for it

      try_delete(os.path.join(self.get_dir(), 'src.cpp.o.js'))
      output = Popen([PYTHON, EMCC, path_from_root('tests', 'dlmalloc_test.c'), '-s', 'TOTAL_MEMORY=' + str(128*1024*1024),
                      '-o', os.path.join(self.get_dir(), 'src.cpp.o.js')], stdout=PIPE, stderr=self.stderr_redirect).communicate()

      self.do_run('x', '*1,0*', ['200', '1'], no_build=True)
      self.do_run('x', '*400,0*', ['400', '400'], no_build=True)

      # The same for new and all its variants
      src = open(path_from_root('tests', 'new.cpp')).read()
      for new, delete in [
        ('malloc(100)', 'free'),
        ('new char[100]', 'delete[]'),
        ('new Structy', 'delete'),
        ('new int', 'delete'),
        ('new Structy[10]', 'delete[]'),
      ]:
        self.do_run(src.replace('{{{ NEW }}}', new).replace('{{{ DELETE }}}', delete), '*1,0*')

  def test_dlmalloc_partial(self):
    if self.emcc_args is None: return self.skip('only emcc will link in dlmalloc')
    # present part of the symbols of dlmalloc, not all
    src = open(path_from_root('tests', 'new.cpp')).read().replace('{{{ NEW }}}', 'new int').replace('{{{ DELETE }}}', 'delete') + '''
void *
operator new(size_t size)
{
printf("new %d!\\n", size);
return malloc(size);
}
'''
    self.do_run(src, 'new 4!\n*1,0*')

  def test_dlmalloc_partial_2(self):
    if self.emcc_args is None or 'SAFE_HEAP' in str(self.emcc_args) or 'CHECK_HEAP_ALIGN' in str(self.emcc_args): return self.skip('only emcc will link in dlmalloc, and we do unsafe stuff')
    # present part of the symbols of dlmalloc, not all. malloc is harder to link than new which is weak.
    src = r'''
      #include <stdio.h>
      #include <stdlib.h>
      void *malloc(size_t size)
      {
        return (void*)123;
      }
      int main() {
        void *x = malloc(10);
        printf("got %p\n", x);
        free(x);
        printf("freed the faker\n");
        return 1;
      }
'''
    self.do_run(src, 'got 0x7b\nfreed')

  def test_libcxx(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    self.do_run(open(path_from_root('tests', 'hashtest.cpp')).read(),
                 'june -> 30\nPrevious (in alphabetical order) is july\nNext (in alphabetical order) is march')

    self.do_run('''
      #include <set>
      #include <stdio.h>
      int main() {
        std::set<int> *fetchOriginatorNums = new std::set<int>();
        fetchOriginatorNums->insert(171);
        printf("hello world\\n");
        return 0;
      }
      ''', 'hello world');

  def test_typeid(self):
    self.do_run(r'''
      #include <stdio.h>
      #include <string.h>
      #include <typeinfo>
      int main() {
        printf("*\n");
        #define MAX 100
        int ptrs[MAX];
        int groups[MAX];
        memset(ptrs, 0, MAX*sizeof(int));
        memset(groups, 0, MAX*sizeof(int));
        int next_group = 1;
        #define TEST(X) { \
          int ptr = (int)&typeid(X); \
          int group = 0; \
          int i; \
          for (i = 0; i < MAX; i++) { \
            if (!groups[i]) break; \
            if (ptrs[i] == ptr) { \
              group = groups[i]; \
              break; \
            } \
          } \
          if (!group) { \
            groups[i] = group = next_group++; \
            ptrs[i] = ptr; \
          } \
          printf("%s:%d\n", #X, group); \
        }
        TEST(int);
        TEST(unsigned int);
        TEST(unsigned);
        TEST(signed int);
        TEST(long);
        TEST(unsigned long);
        TEST(signed long);
        TEST(long long);
        TEST(unsigned long long);
        TEST(signed long long);
        TEST(short);
        TEST(unsigned short);
        TEST(signed short);
        TEST(char);
        TEST(unsigned char);
        TEST(signed char);
        TEST(float);
        TEST(double);
        TEST(long double);
        TEST(void);
        TEST(void*);
        printf("*\n");
      }
      ''', '''*
int:1
unsigned int:2
unsigned:2
signed int:1
long:3
unsigned long:4
signed long:3
long long:5
unsigned long long:6
signed long long:5
short:7
unsigned short:8
signed short:7
char:9
unsigned char:10
signed char:11
float:12
double:13
long double:14
void:15
void*:16
*
''');

  def test_static_variable(self):
    if self.emcc_args is None: Settings.SAFE_HEAP = 0 # LLVM mixes i64 and i8 in the guard check
    src = '''
      #include <stdio.h>

      struct DATA
      {
          int value;

          DATA()
          {
              value = 0;
          }
      };

      DATA & GetData()
      {
          static DATA data;

          return data;
      }

      int main()
      {
          GetData().value = 10;
          printf( "value:%i", GetData().value );
      }
    '''
    self.do_run(src, 'value:10')

  def test_fakestat(self):
    src = r'''
      #include <stdio.h>
      struct stat { int x, y; };
      int main() {
        stat s;
        s.x = 10;
        s.y = 22;
        printf("*%d,%d*\n", s.x, s.y);
      }
    '''
    self.do_run(src, '*10,22*')

  def test_mmap(self):
    if self.emcc_args is None: return self.skip('requires emcc')

    Settings.TOTAL_MEMORY = 128*1024*1024

    src = '''
      #include <stdio.h>
      #include <sys/mman.h>
      #include <assert.h>

      int main(int argc, char *argv[]) {
          for (int i = 0; i < 10; i++) {
            int* map = (int*)mmap(0, 5000, PROT_READ | PROT_WRITE,
                    MAP_SHARED | MAP_ANON, -1, 0);
            /* TODO: Should we align to 4k?
            assert(((int)map) % 4096 == 0); // aligned
            */
            assert(munmap(map, 5000) == 0);
          }

          const int NUM_BYTES = 8 * 1024 * 1024;
          const int NUM_INTS = NUM_BYTES / sizeof(int);

          int* map = (int*)mmap(0, NUM_BYTES, PROT_READ | PROT_WRITE,
                  MAP_SHARED | MAP_ANON, -1, 0);
          assert(map != MAP_FAILED);

          int i;

          for (i = 0; i < NUM_INTS; i++) {
              map[i] = i;
          }

          for (i = 0; i < NUM_INTS; i++) {
              assert(map[i] == i);
          }

          assert(munmap(map, NUM_BYTES) == 0);

          printf("hello,world");
          return 0;
      }
    '''
    self.do_run(src, 'hello,world')
    self.do_run(src, 'hello,world', force_c=True)

  def test_mmap_file(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    for extra_args in [[], ['--no-heap-copy']]:
      self.emcc_args += ['--embed-file', 'data.dat'] + extra_args

      open(self.in_dir('data.dat'), 'w').write('data from the file ' + ('.' * 9000))

      src = open(path_from_root('tests', 'mmap_file.c')).read()
      self.do_run(src, '*\ndata from the file .\nfrom the file ......\n*\n')

  def test_cubescript(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    if self.run_name == 'o2':
      self.emcc_args += ['--closure', '1'] # Use closure here for some additional coverage

    Building.COMPILER_TEST_OPTS = filter(lambda x: x != '-g', Building.COMPILER_TEST_OPTS) # remove -g, so we have one test without it by default
    if self.emcc_args is None: Settings.SAFE_HEAP = 0 # Has some actual loads of unwritten-to places, in the C++ code...

    # Overflows happen in hash loop
    Settings.CORRECT_OVERFLOWS = 1
    Settings.CHECK_OVERFLOWS = 0

    if Settings.USE_TYPED_ARRAYS == 2:
      Settings.CORRECT_SIGNS = 1

    self.do_run(path_from_root('tests', 'cubescript'), '*\nTemp is 33\n9\n5\nhello, everyone\n*', main_file='command.cpp')

    if os.environ.get('EMCC_FAST_COMPILER') == '1': return self.skip('skipping extra parts in fastcomp')

    assert 'asm2g' in test_modes
    if self.run_name == 'asm2g':
      results = {}
      original = open('src.cpp.o.js').read()
      results[Settings.ALIASING_FUNCTION_POINTERS] = len(original)
      Settings.ALIASING_FUNCTION_POINTERS = 1 - Settings.ALIASING_FUNCTION_POINTERS
      self.do_run(path_from_root('tests', 'cubescript'), '*\nTemp is 33\n9\n5\nhello, everyone\n*', main_file='command.cpp')
      final = open('src.cpp.o.js').read()
      results[Settings.ALIASING_FUNCTION_POINTERS] = len(final)
      open('original.js', 'w').write(original)
      print results
      assert results[1] < 0.99*results[0]
      assert ' & 3]()' in original, 'small function table exists'
      assert ' & 3]()' not in final, 'small function table does not exist'
      assert ' & 255]()' not in original, 'big function table does not exist'
      assert ' & 255]()' in final, 'big function table exists'

    assert 'asm1' in test_modes
    if self.run_name == 'asm1':
      generated = open('src.cpp.o.js').read()
      main = generated[generated.find('function runPostSets'):]
      main = main[:main.find('\n}')]
      assert main.count('\n') == 7, 'must not emit too many postSets: %d' % main.count('\n')

  def test_simd(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('needs ta2')
    if Settings.ASM_JS: Settings.ASM_JS = 2 # does not validate
    src = r'''
#include <stdio.h>

#include <emscripten/vector.h>

static inline float32x4 __attribute__((always_inline))
_mm_set_ps(const float __Z, const float __Y, const float __X, const float __W)
{
  return (float32x4){ __W, __X, __Y, __Z };
}

static __inline__ float32x4 __attribute__((__always_inline__))
_mm_setzero_ps(void)
{
  return (float32x4){ 0.0, 0.0, 0.0, 0.0 };
}

int main(int argc, char **argv) {
  float data[8];
  for (int i = 0; i < 32; i++) data[i] = (1+i+argc)*(2+i+argc*argc); // confuse optimizer
  {
    float32x4 *a = (float32x4*)&data[0];
    float32x4 *b = (float32x4*)&data[4];
    float32x4 c, d;
    c = *a;
    d = *b;
    printf("1floats! %d, %d, %d, %d   %d, %d, %d, %d\n", (int)c[0], (int)c[1], (int)c[2], (int)c[3], (int)d[0], (int)d[1], (int)d[2], (int)d[3]);
    c = c+d;
    printf("2floats! %d, %d, %d, %d   %d, %d, %d, %d\n", (int)c[0], (int)c[1], (int)c[2], (int)c[3], (int)d[0], (int)d[1], (int)d[2], (int)d[3]);
    d = c*d;
    printf("3floats! %d, %d, %d, %d   %d, %d, %d, %d\n", (int)c[0], (int)c[1], (int)c[2], (int)c[3], (int)d[0], (int)d[1], (int)d[2], (int)d[3]);
    c = _mm_setzero_ps();
    printf("zeros %d, %d, %d, %d\n", (int)c[0], (int)c[1], (int)c[2], (int)c[3]);
  }
  {
    int32x4 *a = (int32x4*)&data[0];
    int32x4 *b = (int32x4*)&data[4];
    int32x4 c, d, e, f;
    c = *a;
    d = *b;
    printf("4ints! %d, %d, %d, %d   %d, %d, %d, %d\n", c[0], c[1], c[2], c[3], d[0], d[1], d[2], d[3]);
    e = c+d;
    f = c-d;
    printf("5ints! %d, %d, %d, %d   %d, %d, %d, %d\n", e[0], e[1], e[2], e[3], f[0], f[1], f[2], f[3]);
    e = c&d;
    f = c|d;
    e = ~c&d;
    f = c^d;
    printf("5intops! %d, %d, %d, %d   %d, %d, %d, %d\n", e[0], e[1], e[2], e[3], f[0], f[1], f[2], f[3]);
  }
  {
    float32x4 c, d, e, f;
    c = _mm_set_ps(9.0, 4.0, 0, -9.0);
    d = _mm_set_ps(10.0, 14.0, -12, -2.0);
    printf("6floats! %d, %d, %d, %d   %d, %d, %d, %d\n", (int)c[0], (int)c[1], (int)c[2], (int)c[3], (int)d[0], (int)d[1], (int)d[2], (int)d[3]);
    printf("7calcs: %d\n", emscripten_float32x4_signmask(c)); // TODO: just not just compilation but output as well
  }

  return 0;
}
    '''

    self.do_run(src, '''1floats! 6, 12, 20, 30   42, 56, 72, 90
2floats! 48, 68, 92, 120   42, 56, 72, 90
3floats! 48, 68, 92, 120   2016, 3808, 6624, 10800
zeros 0, 0, 0, 0
4ints! 1086324736, 1094713344, 1101004800, 1106247680   1109917696, 1113587712, 1116733440, 1119092736
5ints! -2098724864, -2086666240, -2077229056, -2069626880   -23592960, -18874368, -15728640, -12845056
5intops! 36175872, 35651584, 34603008, 33816576   48758784, 52428800, 53477376, 54788096
6floats! -9, 0, 4, 9   -2, -12, 14, 10
''')

  def test_simd2(self):
    if Settings.ASM_JS: Settings.ASM_JS = 2 # does not validate

    self.do_run(r'''
      #include <stdio.h>

      typedef float __m128 __attribute__ ((__vector_size__ (16)));

      static inline __m128 __attribute__((always_inline))
      _mm_set_ps(const float __Z, const float __Y, const float __X, const float __W)
      {
        return (__m128){ __W, __X, __Y, __Z };
      }

      static inline void __attribute__((always_inline))
      _mm_store_ps(float *__P, __m128 __A)
      {
        *(__m128 *)__P = __A;
      }

      static inline __m128 __attribute__((always_inline))
      _mm_add_ps(__m128 __A, __m128 __B)
      {
        return __A + __B;
      }

      using namespace std;

      int main(int argc, char ** argv) {
          float __attribute__((__aligned__(16))) ar[4];
          __m128 v1 = _mm_set_ps(9.0, 4.0, 0, -9.0);
          __m128 v2 = _mm_set_ps(7.0, 3.0, 2.5, 1.0);
          __m128 v3 = _mm_add_ps(v1, v2);
          _mm_store_ps(ar, v3);
          
          for (int i = 0; i < 4; i++) {
              printf("%f\n", ar[i]);
          }
          
          return 0;
      }
      ''', '''-8.000000
2.500000
7.000000
16.000000
''')

  def test_simd3(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('needs ta2')
    if Settings.ASM_JS: Settings.ASM_JS = 2 # does not validate
    src = r'''
    #include <iostream>
    #include <emmintrin.h>
    #include <assert.h>
    #include <stdint.h>
    #include <bitset>

    using namespace std;

    void testSetPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v = _mm_set_ps(1.0, 2.0, 3.0, 4.0);
        _mm_store_ps(ar, v);    
        assert(ar[0] == 4.0);
        assert(ar[1] == 3.0);
        assert(ar[2] == 2.0);
        assert(ar[3] == 1.0);
    }

    void testSet1Ps() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v = _mm_set1_ps(5.5);
        _mm_store_ps(ar, v);    
        assert(ar[0] == 5.5);
        assert(ar[1] == 5.5);
        assert(ar[2] == 5.5);
        assert(ar[3] == 5.5);
    }

    void testSetZeroPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v = _mm_setzero_ps();
        _mm_store_ps(ar, v);    
        assert(ar[0] == 0);
        assert(ar[1] == 0);
        assert(ar[2] == 0);
        assert(ar[3] == 0);
    }

    void testSetEpi32() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v = _mm_set_epi32(5, 7, 126, 381);
        _mm_store_si128((__m128i *)ar, v);
        assert(ar[0] == 381);
        assert(ar[1] == 126);
        assert(ar[2] == 7);
        assert(ar[3] == 5);
        v = _mm_set_epi32(0x55555555, 0xaaaaaaaa, 0xffffffff, 0x12345678);
        _mm_store_si128((__m128i *)ar, v);
        assert(ar[0] == 0x12345678);
        assert(ar[1] == 0xffffffff);
        assert(ar[2] == 0xaaaaaaaa);
        assert(ar[3] == 0x55555555);
    }

    void testSet1Epi32() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v = _mm_set1_epi32(-5);
        _mm_store_si128((__m128i *)ar, v);    
        assert(ar[0] == -5);
        assert(ar[1] == -5);
        assert(ar[2] == -5);
        assert(ar[3] == -5);
    }

    void testSetZeroSi128() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v = _mm_setzero_si128();
        _mm_store_si128((__m128i *)ar, v);    
        assert(ar[0] == 0);
        assert(ar[1] == 0);
        assert(ar[2] == 0);
        assert(ar[3] == 0);
    }

    void testBitCasts() {
        int32_t __attribute__((__aligned__(16))) ar1[4];
        float __attribute__((__aligned__(16))) ar2[4];
        __m128i v1 = _mm_set_epi32(0x3f800000, 0x40000000, 0x40400000, 0x40800000);
        __m128 v2 = _mm_castsi128_ps(v1);
        _mm_store_ps(ar2, v2);
        assert(ar2[0] == 4.0);
        assert(ar2[1] == 3.0);
        assert(ar2[2] == 2.0);
        assert(ar2[3] == 1.0);
        v2 = _mm_set_ps(5.0, 6.0, 7.0, 8.0);
        v1 = _mm_castps_si128(v2);
        _mm_store_si128((__m128i *)ar1, v1);
        assert(ar1[0] == 0x41000000);
        assert(ar1[1] == 0x40e00000);
        assert(ar1[2] == 0x40c00000);
        assert(ar1[3] == 0x40a00000);
        float w = 0;
        float z = -278.3;
        float y = 5.2;
        float x = -987654321; 
        v1 = _mm_castps_si128(_mm_set_ps(w, z, y, x));
        _mm_store_ps(ar2, _mm_castsi128_ps(v1));
        assert(ar2[0] == x);
        assert(ar2[1] == y);
        assert(ar2[2] == z);
        assert(ar2[3] == w);
        /*
        std::bitset<sizeof(float)*CHAR_BIT> bits1x(*reinterpret_cast<unsigned long*>(&(ar2[0])));
        std::bitset<sizeof(float)*CHAR_BIT> bits1y(*reinterpret_cast<unsigned long*>(&(ar2[1])));
        std::bitset<sizeof(float)*CHAR_BIT> bits1z(*reinterpret_cast<unsigned long*>(&(ar2[2])));
        std::bitset<sizeof(float)*CHAR_BIT> bits1w(*reinterpret_cast<unsigned long*>(&(ar2[3])));
        std::bitset<sizeof(float)*CHAR_BIT> bits2x(*reinterpret_cast<unsigned long*>(&x));
        std::bitset<sizeof(float)*CHAR_BIT> bits2y(*reinterpret_cast<unsigned long*>(&y));
        std::bitset<sizeof(float)*CHAR_BIT> bits2z(*reinterpret_cast<unsigned long*>(&z));
        std::bitset<sizeof(float)*CHAR_BIT> bits2w(*reinterpret_cast<unsigned long*>(&w));
        assert(bits1x == bits2x);
        assert(bits1y == bits2y);
        assert(bits1z == bits2z);
        assert(bits1w == bits2w);
        */
        v2 = _mm_castsi128_ps(_mm_set_epi32(0xffffffff, 0, 0x5555cccc, 0xaaaaaaaa));
        _mm_store_si128((__m128i *)ar1, _mm_castps_si128(v2));
        assert(ar1[0] == 0xaaaaaaaa);
        assert(ar1[1] == 0x5555cccc);
        assert(ar1[2] == 0);
        assert(ar1[3] == 0xffffffff);
    }

    void testConversions() {
        int32_t __attribute__((__aligned__(16))) ar1[4];
        float __attribute__((__aligned__(16))) ar2[4];
        __m128i v1 = _mm_set_epi32(0, -3, -517, 256);
        __m128 v2 = _mm_cvtepi32_ps(v1);
        _mm_store_ps(ar2, v2);
        assert(ar2[0] == 256.0);
        assert(ar2[1] == -517.0);
        assert(ar2[2] == -3.0);
        assert(ar2[3] == 0);
        v2 = _mm_set_ps(5.0, 6.0, 7.45, -8.0);
        v1 = _mm_cvtps_epi32(v2);
        _mm_store_si128((__m128i *)ar1, v1);
        assert(ar1[0] == -8);
        assert(ar1[1] == 7);
        assert(ar1[2] == 6);
        assert(ar1[3] == 5);
    }

    void testMoveMaskPs() {
        __m128 v = _mm_castsi128_ps(_mm_set_epi32(0xffffffff, 0xffffffff, 0, 0xffffffff));
        int mask = _mm_movemask_ps(v);
        assert(mask == 13);
    }

    void testAddPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(4.0, 3.0, 2.0, 1.0);
        __m128 v2 = _mm_set_ps(10.0, 20.0, 30.0, 40.0);
        __m128 v = _mm_add_ps(v1, v2);
        _mm_store_ps(ar, v);
        assert(ar[0] == 41.0);
        assert(ar[1] == 32.0);
        assert(ar[2] == 23.0);
        assert(ar[3] == 14.0);
    }

    void testSubPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(4.0, 3.0, 2.0, 1.0);
        __m128 v2 = _mm_set_ps(10.0, 20.0, 30.0, 40.0);
        __m128 v = _mm_sub_ps(v1, v2);
        _mm_store_ps(ar, v);
        assert(ar[0] == -39.0);
        assert(ar[1] == -28.0);
        assert(ar[2] == -17.0);
        assert(ar[3] == -6.0);
    }

    void testMulPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(4.0, 3.0, 2.0, 1.0);
        __m128 v2 = _mm_set_ps(10.0, 20.0, 30.0, 40.0);
        __m128 v = _mm_mul_ps(v1, v2);
        _mm_store_ps(ar, v);
        assert(ar[0] == 40.0);
        assert(ar[1] == 60.0);
        assert(ar[2] == 60.0);
        assert(ar[3] == 40.0);
    }

    void testDivPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(4.0, 9.0, 8.0, 1.0);
        __m128 v2 = _mm_set_ps(2.0, 3.0, 1.0, 0.5);
        __m128 v = _mm_div_ps(v1, v2);
        _mm_store_ps(ar, v);
        assert(ar[0] == 2.0);
        assert(ar[1] == 8.0);
        assert(ar[2] == 3.0);
        assert(ar[3] == 2.0);
    }

    void testMinPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(-20.0, 10.0, 30.0, 0.5);
        __m128 v2 = _mm_set_ps(2.0, 1.0, 50.0, 0.0);
        __m128 v = _mm_min_ps(v1, v2);
        _mm_store_ps(ar, v);
        assert(ar[0] == 0.0);
        assert(ar[1] == 30.0);
        assert(ar[2] == 1.0);
        assert(ar[3] == -20.0);
    }

    void testMaxPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(-20.0, 10.0, 30.0, 0.5);
        __m128 v2 = _mm_set_ps(2.5, 5.0, 55.0, 1.0);
        __m128 v = _mm_max_ps(v1, v2);
        _mm_store_ps(ar, v);
        assert(ar[0] == 1.0);
        assert(ar[1] == 55.0);
        assert(ar[2] == 10.0);
        assert(ar[3] == 2.5);
    }

    void testSqrtPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(16.0, 9.0, 4.0, 1.0);
        __m128 v = _mm_sqrt_ps(v1);
        _mm_store_ps(ar, v);
        assert(ar[0] == 1.0);
        assert(ar[1] == 2.0);
        assert(ar[2] == 3.0);
        assert(ar[3] == 4.0);
    }

    void testCmpLtPs() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(1.0, 2.0, 0.1, 0.001);
        __m128 v2 = _mm_set_ps(2.0, 2.0, 0.001, 0.1);
        __m128 v = _mm_cmplt_ps(v1, v2);
        _mm_store_si128((__m128i *)ar, _mm_castps_si128(v));
        assert(ar[0] == 0xffffffff);
        assert(ar[1] == 0);
        assert(ar[2] == 0);
        assert(ar[3] == 0xffffffff);
        assert(_mm_movemask_ps(v) == 9);
    }

    void testCmpLePs() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(1.0, 2.0, 0.1, 0.001);
        __m128 v2 = _mm_set_ps(2.0, 2.0, 0.001, 0.1);
        __m128 v = _mm_cmple_ps(v1, v2);
        _mm_store_si128((__m128i *)ar, _mm_castps_si128(v));
        assert(ar[0] == 0xffffffff);
        assert(ar[1] == 0);
        assert(ar[2] == 0xffffffff);
        assert(ar[3] == 0xffffffff);
        assert(_mm_movemask_ps(v) == 13);
    }

    void testCmpEqPs() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(1.0, 2.0, 0.1, 0.001);
        __m128 v2 = _mm_set_ps(2.0, 2.0, 0.001, 0.1);
        __m128 v = _mm_cmpeq_ps(v1, v2);
        _mm_store_si128((__m128i *)ar, _mm_castps_si128(v));
        assert(ar[0] == 0);
        assert(ar[1] == 0);
        assert(ar[2] == 0xffffffff);
        assert(ar[3] == 0);
        assert(_mm_movemask_ps(v) == 4);
    }

    void testCmpGePs() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(1.0, 2.0, 0.1, 0.001);
        __m128 v2 = _mm_set_ps(2.0, 2.0, 0.001, 0.1);
        __m128 v = _mm_cmpge_ps(v1, v2);
        _mm_store_si128((__m128i *)ar, _mm_castps_si128(v));
        assert(ar[0] == 0);
        assert(ar[1] == 0xffffffff);
        assert(ar[2] == 0xffffffff);
        assert(ar[3] == 0);
        assert(_mm_movemask_ps(v) == 6);
    }

    void testCmpGtPs() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(1.0, 2.0, 0.1, 0.001);
        __m128 v2 = _mm_set_ps(2.0, 2.0, 0.001, 0.1);
        __m128 v = _mm_cmpgt_ps(v1, v2);
        _mm_store_si128((__m128i *)ar, _mm_castps_si128(v));
        assert(ar[0] == 0);
        assert(ar[1] == 0xffffffff);
        assert(ar[2] == 0);
        assert(ar[3] == 0);
        assert(_mm_movemask_ps(v) == 2);
    }

    void testAndPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(425, -501, -32, 68);
        __m128 v2 = _mm_castsi128_ps(_mm_set_epi32(0xffffffff, 0xffffffff, 0, 0xffffffff));
        __m128 v = _mm_and_ps(v1, v2);
        _mm_store_ps(ar, v);
        assert(ar[0] == 68);
        assert(ar[1] == 0);
        assert(ar[2] == -501);
        assert(ar[3] == 425);
        int32_t __attribute__((__aligned__(16))) ar2[4];
        v1 = _mm_castsi128_ps(_mm_set_epi32(0xaaaaaaaa, 0xaaaaaaaa, -1431655766, 0xaaaaaaaa));
        v2 = _mm_castsi128_ps(_mm_set_epi32(0x55555555, 0x55555555,  0x55555555, 0x55555555));
        v = _mm_and_ps(v1, v2);
        _mm_store_si128((__m128i *)ar2, _mm_castps_si128(v));
        assert(ar2[0] == 0);
        assert(ar2[1] == 0);
        assert(ar2[2] == 0);
        assert(ar2[3] == 0);
    }

    void testAndNotPs() {
        float __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_set_ps(425, -501, -32, 68);
        __m128 v2 = _mm_castsi128_ps(_mm_set_epi32(0xffffffff, 0xffffffff, 0, 0xffffffff));
        __m128 v = _mm_andnot_ps(v2, v1);
        _mm_store_ps(ar, v);
        assert(ar[0] == 0);
        assert(ar[1] == -32);
        assert(ar[2] == 0);
        assert(ar[3] == 0);
        int32_t __attribute__((__aligned__(16))) ar2[4];
        v1 = _mm_castsi128_ps(_mm_set_epi32(0xaaaaaaaa, 0xaaaaaaaa, -1431655766, 0xaaaaaaaa));
        v2 = _mm_castsi128_ps(_mm_set_epi32(0x55555555, 0x55555555,  0x55555555, 0x55555555));
        v = _mm_andnot_ps(v1, v2);
        _mm_store_si128((__m128i *)ar2, _mm_castps_si128(v));
        assert(ar2[0] == 0x55555555);
        assert(ar2[1] == 0x55555555);
        assert(ar2[2] == 0x55555555);
        assert(ar2[3] == 0x55555555);
    }

    void testOrPs() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_castsi128_ps(_mm_set_epi32(0xaaaaaaaa, 0xaaaaaaaa, 0xffffffff, 0));
        __m128 v2 = _mm_castsi128_ps(_mm_set_epi32(0x55555555, 0x55555555, 0x55555555, 0x55555555));
        __m128 v = _mm_or_ps(v1, v2);
        _mm_store_si128((__m128i *)ar, _mm_castps_si128(v));
        assert(ar[0] == 0x55555555);
        assert(ar[1] == 0xffffffff);
        assert(ar[2] == 0xffffffff);
        assert(ar[3] == 0xffffffff);
    }

    void testXorPs() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128 v1 = _mm_castsi128_ps(_mm_set_epi32(0xaaaaaaaa, 0xaaaaaaaa, 0xffffffff, 0));
        __m128 v2 = _mm_castsi128_ps(_mm_set_epi32(0x55555555, 0x55555555, 0x55555555, 0x55555555));
        __m128 v = _mm_xor_ps(v1, v2);
        _mm_store_si128((__m128i *)ar, _mm_castps_si128(v));
        assert(ar[0] == 0x55555555);
        assert(ar[1] == 0xaaaaaaaa);
        assert(ar[2] == 0xffffffff);
        assert(ar[3] == 0xffffffff);
    }

    void testAndSi128() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v1 = _mm_set_epi32(0xaaaaaaaa, 0xaaaaaaaa, -1431655766, 0xaaaaaaaa);
        __m128i v2 = _mm_set_epi32(0x55555555, 0x55555555,  0x55555555, 0x55555555);
        __m128i v = _mm_and_si128(v1, v2);
        _mm_store_si128((__m128i *)ar, v);
        assert(ar[0] == 0);
        assert(ar[1] == 0);
        assert(ar[2] == 0);
        assert(ar[3] == 0);
    }

    void testAndNotSi128() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v1 = _mm_set_epi32(0xaaaaaaaa, 0xaaaaaaaa, -1431655766, 0xaaaaaaaa);
        __m128i v2 = _mm_set_epi32(0x55555555, 0x55555555,  0x55555555, 0x55555555);
        __m128i v = _mm_andnot_si128(v1, v2);
        _mm_store_si128((__m128i *)ar, v);
        assert(ar[0] == 0x55555555);
        assert(ar[1] == 0x55555555);
        assert(ar[2] == 0x55555555);
        assert(ar[3] == 0x55555555);
    }

    void testOrSi128() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v1 = _mm_set_epi32(0xaaaaaaaa, 0xaaaaaaaa, 0xffffffff, 0);
        __m128i v2 = _mm_set_epi32(0x55555555, 0x55555555, 0x55555555, 0x55555555);
        __m128i v = _mm_or_si128(v1, v2);
        _mm_store_si128((__m128i *)ar, v);
        assert(ar[0] == 0x55555555);
        assert(ar[1] == 0xffffffff);
        assert(ar[2] == 0xffffffff);
        assert(ar[3] == 0xffffffff);
    }

    void testXorSi128() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v1 = _mm_set_epi32(0xaaaaaaaa, 0xaaaaaaaa, 0xffffffff, 0);
        __m128i v2 = _mm_set_epi32(0x55555555, 0x55555555, 0x55555555, 0x55555555);
        __m128i v = _mm_xor_si128(v1, v2);
        _mm_store_si128((__m128i *)ar, v);
        assert(ar[0] == 0x55555555);
        assert(ar[1] == 0xaaaaaaaa);
        assert(ar[2] == 0xffffffff);
        assert(ar[3] == 0xffffffff);
    }

    void testAddEpi32() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v1 = _mm_set_epi32(4, 3, 2, 1);
        __m128i v2 = _mm_set_epi32(10, 20, 30, 40);
        __m128i v = _mm_add_epi32(v1, v2);
        _mm_store_si128((__m128i *)ar, v);
        assert(ar[0] == 41);
        assert(ar[1] == 32);
        assert(ar[2] == 23);
        assert(ar[3] == 14);
    }

    void testSubEpi32() {
        int32_t __attribute__((__aligned__(16))) ar[4];
        __m128i v1 = _mm_set_epi32(4, 3, 2, 1);
        __m128i v2 = _mm_set_epi32(10, 20, 30, 40);
        __m128i v = _mm_sub_epi32(v1, v2);
        _mm_store_si128((__m128i *)ar, v);
        assert(ar[0] == -39);
        assert(ar[1] == -28);
        assert(ar[2] == -17);
        assert(ar[3] == -6);
    }

    int main(int argc, char ** argv) {
        testSetPs();
        testSet1Ps();
        testSetZeroPs();
        testSetEpi32();
        testSet1Epi32();
        testSetZeroSi128();
        testBitCasts();
        testConversions();
        testMoveMaskPs();
        testAddPs();
        testSubPs();
        testMulPs();
        testDivPs();
        testMaxPs();
        testMinPs();
        testSqrtPs();
        testCmpLtPs();
        testCmpLePs();
        testCmpEqPs();
        testCmpGePs();
        testCmpGtPs();
        testAndPs();
        testAndNotPs();
        testOrPs();
        testXorPs();
        testAndSi128();
        testAndNotSi128();
        testOrSi128();
        testXorSi128();
        testAddEpi32();
        testSubEpi32();
        printf("DONE");
        return 0;
    }
    '''

    self.do_run(src, 'DONE')


  def test_gcc_unmangler(self):
    Settings.NAMED_GLOBALS = 1 # test coverage for this

    Building.COMPILER_TEST_OPTS += ['-I' + path_from_root('third_party')]

    self.do_run(open(path_from_root('third_party', 'gcc_demangler.c')).read(), '*d_demangle(char const*, int, unsigned int*)*', args=['_ZL10d_demanglePKciPj'])

    #### Code snippet that is helpful to search for nonportable optimizations ####
    #global LLVM_OPT_OPTS
    #for opt in ['-aa-eval', '-adce', '-always-inline', '-argpromotion', '-basicaa', '-basiccg', '-block-placement', '-break-crit-edges', '-codegenprepare', '-constmerge', '-constprop', '-correlated-propagation', '-count-aa', '-dce', '-deadargelim', '-deadtypeelim', '-debug-aa', '-die', '-domfrontier', '-domtree', '-dse', '-extract-blocks', '-functionattrs', '-globaldce', '-globalopt', '-globalsmodref-aa', '-gvn', '-indvars', '-inline', '-insert-edge-profiling', '-insert-optimal-edge-profiling', '-instcombine', '-instcount', '-instnamer', '-internalize', '-intervals', '-ipconstprop', '-ipsccp', '-iv-users', '-jump-threading', '-lazy-value-info', '-lcssa', '-lda', '-libcall-aa', '-licm', '-lint', '-live-values', '-loop-deletion', '-loop-extract', '-loop-extract-single', '-loop-index-split', '-loop-reduce', '-loop-rotate', '-loop-unroll', '-loop-unswitch', '-loops', '-loopsimplify', '-loweratomic', '-lowerinvoke', '-lowersetjmp', '-lowerswitch', '-mem2reg', '-memcpyopt', '-memdep', '-mergefunc', '-mergereturn', '-module-debuginfo', '-no-aa', '-no-profile', '-partial-inliner', '-partialspecialization', '-pointertracking', '-postdomfrontier', '-postdomtree', '-preverify', '-prune-eh', '-reassociate', '-reg2mem', '-regions', '-scalar-evolution', '-scalarrepl', '-sccp', '-scev-aa', '-simplify-libcalls', '-simplify-libcalls-halfpowr', '-simplifycfg', '-sink', '-split-geps', '-sretpromotion', '-strip', '-strip-dead-debug-info', '-strip-dead-prototypes', '-strip-debug-declare', '-strip-nondebug', '-tailcallelim', '-tailduplicate', '-targetdata', '-tbaa']:
    #  LLVM_OPT_OPTS = [opt]
    #  try:
    #    self.do_run(path_from_root(['third_party']), '*d_demangle(char const*, int, unsigned int*)*', args=['_ZL10d_demanglePKciPj'], main_file='gcc_demangler.c')
    #    print opt, "ok"
    #  except:
    #    print opt, "FAIL"

  def test_lua(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    if Settings.QUANTUM_SIZE == 1: return self.skip('TODO: make this work')

    self.do_run('',
                'hello lua world!\n17\n1\n2\n3\n4\n7',
                args=['-e', '''print("hello lua world!");print(17);for x = 1,4 do print(x) end;print(10-3)'''],
                libraries=self.get_library('lua', [os.path.join('src', 'lua'), os.path.join('src', 'liblua.a')], make=['make', 'generic'], configure=None),
                includes=[path_from_root('tests', 'lua')],
                output_nicerizer=lambda string, err: (string + err).replace('\n\n', '\n').replace('\n\n', '\n'))

  def get_freetype(self):
    Settings.DEAD_FUNCTIONS += ['_inflateEnd', '_inflate', '_inflateReset', '_inflateInit2_']

    return self.get_library('freetype',
                            os.path.join('objs', '.libs', 'libfreetype.a'))

  def test_freetype(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    if Settings.QUANTUM_SIZE == 1: return self.skip('TODO: Figure out and try to fix')

    assert 'asm2g' in test_modes
    if self.run_name == 'asm2g':
      Settings.ALIASING_FUNCTION_POINTERS = 1 - Settings.ALIASING_FUNCTION_POINTERS # flip for some more coverage here

    if Settings.CORRECT_SIGNS == 0: Settings.CORRECT_SIGNS = 1 # Not sure why, but needed

    post = '''
def process(filename):
  import tools.shared as shared
  # Embed the font into the document
  src = open(filename, 'r').read().replace(
    '// {{PRE_RUN_ADDITIONS}}',
    "FS.createDataFile('/', 'font.ttf', %s, true, false);" % str(
      map(ord, open(shared.path_from_root('tests', 'freetype', 'LiberationSansBold.ttf'), 'rb').read())
    )
  )
  open(filename, 'w').write(src)
'''

    # Not needed for js, but useful for debugging
    shutil.copyfile(path_from_root('tests', 'freetype', 'LiberationSansBold.ttf'), os.path.join(self.get_dir(), 'font.ttf'))

    # Main
    for outlining in [0, 5000]:
      Settings.OUTLINING_LIMIT = outlining
      print >> sys.stderr, 'outlining:', outlining
      self.do_run(open(path_from_root('tests', 'freetype', 'main.c'), 'r').read(),
                   open(path_from_root('tests', 'freetype', 'ref.txt'), 'r').read(),
                   ['font.ttf', 'test!', '150', '120', '25'],
                   libraries=self.get_freetype(),
                   includes=[path_from_root('tests', 'freetype', 'include')],
                   post_build=post)

    # github issue 324
    print '[issue 324]'
    self.do_run(open(path_from_root('tests', 'freetype', 'main_2.c'), 'r').read(),
                 open(path_from_root('tests', 'freetype', 'ref_2.txt'), 'r').read(),
                 ['font.ttf', 'w', '32', '32', '25'],
                 libraries=self.get_freetype(),
                 includes=[path_from_root('tests', 'freetype', 'include')],
                 post_build=post)

    print '[issue 324 case 2]'
    self.do_run(open(path_from_root('tests', 'freetype', 'main_3.c'), 'r').read(),
                 open(path_from_root('tests', 'freetype', 'ref_3.txt'), 'r').read(),
                 ['font.ttf', 'W', '32', '32', '0'],
                 libraries=self.get_freetype(),
                 includes=[path_from_root('tests', 'freetype', 'include')],
                 post_build=post)

    print '[issue 324 case 3]'
    self.do_run('',
                 open(path_from_root('tests', 'freetype', 'ref_4.txt'), 'r').read(),
                 ['font.ttf', 'ea', '40', '32', '0'],
                 no_build=True)

  def test_sqlite(self):
    # gcc -O3 -I/home/alon/Dev/emscripten/tests/sqlite -ldl src.c
    if self.emcc_args is None: return self.skip('Very slow without ta2, and we would also need to include dlmalloc manually without emcc')
    if not self.is_le32(): return self.skip('fails on x86 due to a legalization issue on llvm 3.3')
    if Settings.QUANTUM_SIZE == 1: return self.skip('TODO FIXME')
    self.banned_js_engines = [NODE_JS] # OOM in older node

    Settings.CORRECT_SIGNS = 1
    Settings.CORRECT_OVERFLOWS = 0
    Settings.CORRECT_ROUNDINGS = 0
    if self.emcc_args is None: Settings.SAFE_HEAP = 0 # uses time.h to set random bytes, other stuff
    Settings.DISABLE_EXCEPTION_CATCHING = 1
    Settings.FAST_MEMORY = 4*1024*1024
    Settings.EXPORTED_FUNCTIONS += ['_sqlite3_open', '_sqlite3_close', '_sqlite3_exec', '_sqlite3_free', '_callback'];
    if Settings.ASM_JS == 1 and '-g' in self.emcc_args:
      print "disabling inlining" # without registerize (which -g disables), we generate huge amounts of code
      Settings.INLINING_LIMIT = 50

    self.do_run(r'''
                      #define SQLITE_DISABLE_LFS
                      #define LONGDOUBLE_TYPE double
                      #define SQLITE_INT64_TYPE long long int
                      #define SQLITE_THREADSAFE 0
                 ''' + open(path_from_root('tests', 'sqlite', 'sqlite3.c'), 'r').read() +
                       open(path_from_root('tests', 'sqlite', 'benchmark.c'), 'r').read(),
                 open(path_from_root('tests', 'sqlite', 'benchmark.txt'), 'r').read(),
                 includes=[path_from_root('tests', 'sqlite')],
                 force_c=True)

  def test_zlib(self):
    if not Settings.USE_TYPED_ARRAYS == 2: return self.skip('works in general, but cached build will be optimized and fail, so disable this')

    if Settings.ASM_JS:
      self.banned_js_engines = [NODE_JS] # TODO investigate

    if self.emcc_args is not None and '-O2' in self.emcc_args and 'ASM_JS=0' not in self.emcc_args: # without asm, closure minifies Math.imul badly
      self.emcc_args += ['--closure', '1'] # Use closure here for some additional coverage

    Settings.CORRECT_SIGNS = 1

    self.do_run(open(path_from_root('tests', 'zlib', 'example.c'), 'r').read(),
                 open(path_from_root('tests', 'zlib', 'ref.txt'), 'r').read(),
                 libraries=self.get_library('zlib', os.path.join('libz.a'), make_args=['libz.a']),
                 includes=[path_from_root('tests', 'zlib')],
                 force_c=True)

  def test_the_bullet(self): # Called thus so it runs late in the alphabetical cycle... it is long
    if self.emcc_args is None: return self.skip('requires emcc')
    if Building.LLVM_OPTS and self.emcc_args is None: Settings.SAFE_HEAP = 0 # Optimizations make it so we do not have debug info on the line we need to ignore

    Settings.DEAD_FUNCTIONS = ['__ZSt9terminatev']

    # Note: this is also a good test of per-file and per-line changes (since we have multiple files, and correct specific lines)
    if Settings.SAFE_HEAP:
      # Ignore bitfield warnings
      Settings.SAFE_HEAP = 3
      Settings.SAFE_HEAP_LINES = ['btVoronoiSimplexSolver.h:40', 'btVoronoiSimplexSolver.h:41',
                                  'btVoronoiSimplexSolver.h:42', 'btVoronoiSimplexSolver.h:43']

    for use_cmake in [False, True]: # If false, use a configure script to configure Bullet build.
      print 'cmake', use_cmake
      # Windows cannot run configure sh scripts.
      if WINDOWS and not use_cmake:
        continue

      def test():
        self.do_run(open(path_from_root('tests', 'bullet', 'Demos', 'HelloWorld', 'HelloWorld.cpp'), 'r').read(),
                     [open(path_from_root('tests', 'bullet', 'output.txt'), 'r').read(), # different roundings
                      open(path_from_root('tests', 'bullet', 'output2.txt'), 'r').read(),
                      open(path_from_root('tests', 'bullet', 'output3.txt'), 'r').read()],
                     libraries=get_bullet_library(self, use_cmake),
                     includes=[path_from_root('tests', 'bullet', 'src')])
      test()

      assert 'asm2g' in test_modes
      if self.run_name == 'asm2g' and not use_cmake:
        # Test forced alignment
        print >> sys.stderr, 'testing FORCE_ALIGNED_MEMORY'
        old = open('src.cpp.o.js').read()
        Settings.FORCE_ALIGNED_MEMORY = 1
        test()
        new = open('src.cpp.o.js').read()
        print len(old), len(new), old.count('tempBigInt'), new.count('tempBigInt')
        assert len(old) > len(new)
        assert old.count('tempBigInt') > new.count('tempBigInt')

  def test_poppler(self):
    if self.emcc_args is None: return self.skip('very slow, we only do this in emcc runs')

    Settings.CORRECT_OVERFLOWS = 1
    Settings.CORRECT_SIGNS = 1

    Building.COMPILER_TEST_OPTS += [
      '-I' + path_from_root('tests', 'freetype', 'include'),
      '-I' + path_from_root('tests', 'poppler', 'include'),
    ]

    Settings.INVOKE_RUN = 0 # We append code that does run() ourselves

    # See post(), below
    input_file = open(os.path.join(self.get_dir(), 'paper.pdf.js'), 'w')
    input_file.write(str(map(ord, open(path_from_root('tests', 'poppler', 'paper.pdf'), 'rb').read())))
    input_file.close()

    post = '''
def process(filename):
  # To avoid loading this large file to memory and altering it, we simply append to the end
  src = open(filename, 'a')
  src.write(
    \'\'\'
      FS.createDataFile('/', 'paper.pdf', eval(Module.read('paper.pdf.js')), true, false);
      Module.callMain(Module.arguments);
      Module.print("Data: " + JSON.stringify(FS.root.contents['filename-1.ppm'].contents.map(function(x) { return unSign(x, 8) })));
    \'\'\'
  )
  src.close()
'''

    #fontconfig = self.get_library('fontconfig', [os.path.join('src', '.libs', 'libfontconfig.a')]) # Used in file, but not needed, mostly

    freetype = self.get_freetype()

    poppler = self.get_library('poppler',
                               [os.path.join('utils', 'pdftoppm.o'),
                                os.path.join('utils', 'parseargs.o'),
                                os.path.join('poppler', '.libs', 'libpoppler.a')],
                               env_init={ 'FONTCONFIG_CFLAGS': ' ', 'FONTCONFIG_LIBS': ' ' },
                               configure_args=['--disable-libjpeg', '--disable-libpng', '--disable-poppler-qt', '--disable-poppler-qt4', '--disable-cms', '--disable-cairo-output', '--disable-abiword-output', '--enable-shared=no'])

    # Combine libraries

    combined = os.path.join(self.get_dir(), 'poppler-combined.bc')
    Building.link(poppler + freetype, combined)

    self.do_ll_run(combined,
                   map(ord, open(path_from_root('tests', 'poppler', 'ref.ppm'), 'r').read()).__str__().replace(' ', ''),
                   args='-scale-to 512 paper.pdf filename'.split(' '),
                   post_build=post)
                   #, build_ll_hook=self.do_autodebug)

  def test_openjpeg(self):
    if self.emcc_args is None: return self.skip('needs libc for getopt')

    Building.COMPILER_TEST_OPTS = filter(lambda x: x != '-g', Building.COMPILER_TEST_OPTS) # remove -g, so we have one test without it by default

    if Settings.USE_TYPED_ARRAYS == 2:
      Settings.CORRECT_SIGNS = 1
    else:
      Settings.CORRECT_SIGNS = 2
      Settings.CORRECT_SIGNS_LINES = ["mqc.c:566", "mqc.c:317"]

    post = '''
def process(filename):
  import tools.shared as shared
  original_j2k = shared.path_from_root('tests', 'openjpeg', 'syntensity_lobby_s.j2k')
  src = open(filename, 'r').read().replace(
    '// {{PRE_RUN_ADDITIONS}}',
    "FS.createDataFile('/', 'image.j2k', %s, true, false);" % shared.line_splitter(str(
      map(ord, open(original_j2k, 'rb').read())
    ))
  ).replace(
    '// {{POST_RUN_ADDITIONS}}',
    "Module.print('Data: ' + JSON.stringify(FS.analyzePath('image.raw').object.contents));"
  )
  open(filename, 'w').write(src)
'''

    shutil.copy(path_from_root('tests', 'openjpeg', 'opj_config.h'), self.get_dir())

    lib = self.get_library('openjpeg',
                           [os.path.sep.join('codec/CMakeFiles/j2k_to_image.dir/index.c.o'.split('/')),
                            os.path.sep.join('codec/CMakeFiles/j2k_to_image.dir/convert.c.o'.split('/')),
                            os.path.sep.join('codec/CMakeFiles/j2k_to_image.dir/__/common/color.c.o'.split('/')),
                            os.path.join('bin', 'libopenjpeg.so.1.4.0')],
                           configure=['cmake', '.'],
                           #configure_args=['--enable-tiff=no', '--enable-jp3d=no', '--enable-png=no'],
                           make_args=[]) # no -j 2, since parallel builds can fail

    # We use doubles in JS, so we get slightly different values than native code. So we
    # check our output by comparing the average pixel difference
    def image_compare(output, err):
      # Get the image generated by JS, from the JSON.stringify'd array
      m = re.search('\[[\d, -]*\]', output)
      try:
        js_data = eval(m.group(0))
      except AttributeError:
        print 'Failed to find proper image output in: ' + output
        raise

      js_data = map(lambda x: x if x >= 0 else 256+x, js_data) # Our output may be signed, so unsign it

      # Get the correct output
      true_data = open(path_from_root('tests', 'openjpeg', 'syntensity_lobby_s.raw'), 'rb').read()

      # Compare them
      assert(len(js_data) == len(true_data))
      num = len(js_data)
      diff_total = js_total = true_total = 0
      for i in range(num):
        js_total += js_data[i]
        true_total += ord(true_data[i])
        diff_total += abs(js_data[i] - ord(true_data[i]))
      js_mean = js_total/float(num)
      true_mean = true_total/float(num)
      diff_mean = diff_total/float(num)

      image_mean = 83.265
      #print '[image stats:', js_mean, image_mean, true_mean, diff_mean, num, ']'
      assert abs(js_mean - image_mean) < 0.01
      assert abs(true_mean - image_mean) < 0.01
      assert diff_mean < 0.01

      return output

    self.emcc_args += ['--minify', '0'] # to compare the versions

    def do_test():
      self.do_run(open(path_from_root('tests', 'openjpeg', 'codec', 'j2k_to_image.c'), 'r').read(),
                   'Successfully generated', # The real test for valid output is in image_compare
                   '-i image.j2k -o image.raw'.split(' '),
                   libraries=lib,
                   includes=[path_from_root('tests', 'openjpeg', 'libopenjpeg'),
                             path_from_root('tests', 'openjpeg', 'codec'),
                             path_from_root('tests', 'openjpeg', 'common'),
                             os.path.join(self.get_build_dir(), 'openjpeg')],
                   force_c=True,
                   post_build=post,
                   output_nicerizer=image_compare)#, build_ll_hook=self.do_autodebug)

    do_test()

    # some test coverage for EMCC_DEBUG 1 and 2
    if self.emcc_args and '-O2' in self.emcc_args and 'EMCC_DEBUG' not in os.environ and '-g' in self.emcc_args:
      shutil.copyfile('src.c.o.js', 'release.js')
      try:
        os.environ['EMCC_DEBUG'] = '1'
        print '2'
        do_test()
        shutil.copyfile('src.c.o.js', 'debug1.js')
        os.environ['EMCC_DEBUG'] = '2'
        print '3'
        do_test()
        shutil.copyfile('src.c.o.js', 'debug2.js')
      finally:
        del os.environ['EMCC_DEBUG']
      for debug in [1,2]:
        def clean(text):
          text = text.replace('\n\n', '\n').replace('\n\n', '\n').replace('\n\n', '\n').replace('\n\n', '\n').replace('\n\n', '\n').replace('{\n}', '{}')
          return '\n'.join(sorted(text.split('\n')))
        self.assertIdentical(clean(open('release.js').read()), clean(open('debug%d.js' % debug).read())) # EMCC_DEBUG=1 mode must not generate different code!
        print >> sys.stderr, 'debug check %d passed too' % debug

      try:
        os.environ['EMCC_FORCE_STDLIBS'] = '1'
        print 'EMCC_FORCE_STDLIBS'
        do_test()
      finally:
        del os.environ['EMCC_FORCE_STDLIBS']
      print >> sys.stderr, 'EMCC_FORCE_STDLIBS ok'

      try_delete(CANONICAL_TEMP_DIR)
    else:
      print >> sys.stderr, 'not doing debug check'

  def test_python(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    if Settings.QUANTUM_SIZE == 1: return self.skip('TODO: make this work')
    if not self.is_le32(): return self.skip('fails on non-le32') # FIXME

    #Settings.EXPORTED_FUNCTIONS += ['_PyRun_SimpleStringFlags'] # for the demo

    if self.is_le32():
      bitcode = path_from_root('tests', 'python', 'python.le32.bc')
    else:
      bitcode = path_from_root('tests', 'python', 'python.small.bc')

    self.do_ll_run(bitcode,
                    'hello python world!\n[0, 2, 4, 6]\n5\n22\n5.470000',
                    args=['-S', '-c' '''print "hello python world!"; print [x*2 for x in range(4)]; t=2; print 10-3-t; print (lambda x: x*2)(11); print '%f' % 5.47'''])

  def test_lifetime(self):
    if self.emcc_args is None: return self.skip('test relies on emcc opts')

    self.do_ll_run(path_from_root('tests', 'lifetime.ll'), 'hello, world!\n')
    if '-O1' in self.emcc_args or '-O2' in self.emcc_args:
      assert 'a18' not in open(os.path.join(self.get_dir(), 'src.cpp.o.js')).read(), 'lifetime stuff and their vars must be culled'

  # Test cases in separate files. Note that these files may contain invalid .ll!
  # They are only valid enough for us to read for test purposes, not for llvm-as
  # to process.
  def test_cases(self):
    if Building.LLVM_OPTS: return self.skip("Our code is not exactly 'normal' llvm assembly")

    emcc_args = self.emcc_args

    try:
      os.environ['EMCC_LEAVE_INPUTS_RAW'] = '1'
      Settings.CHECK_OVERFLOWS = 0

      for name in glob.glob(path_from_root('tests', 'cases', '*.ll')):
        shortname = name.replace('.ll', '')
        if '' not in shortname: continue
        if '_ta2' in shortname and not Settings.USE_TYPED_ARRAYS == 2:
          print self.skip('case "%s" only relevant for ta2' % shortname)
          continue
        if '_noasm' in shortname and Settings.ASM_JS:
          print self.skip('case "%s" not relevant for asm.js' % shortname)
          continue
        if '_le32' in shortname and not self.is_le32():
          print self.skip('case "%s" not relevant for non-le32 target' % shortname)
          continue
        self.emcc_args = emcc_args
        if os.path.exists(shortname + '.emcc'):
          if not self.emcc_args: continue
          self.emcc_args = self.emcc_args + json.loads(open(shortname + '.emcc').read())
        print >> sys.stderr, "Testing case '%s'..." % shortname
        output_file = path_from_root('tests', 'cases', shortname + '.txt')
        if Settings.QUANTUM_SIZE == 1:
          q1_output_file = path_from_root('tests', 'cases', shortname + '_q1.txt')
          if os.path.exists(q1_output_file):
            output_file = q1_output_file
        if os.path.exists(output_file):
          output = open(output_file, 'r').read()
        else:
          output = 'hello, world!'
        if output.rstrip() != 'skip':
          self.do_ll_run(path_from_root('tests', 'cases', name), output)
        # Optional source checking, a python script that gets a global generated with the source
        src_checker = path_from_root('tests', 'cases', shortname + '.py')
        if os.path.exists(src_checker):
          generated = open('src.cpp.o.js').read()
          exec(open(src_checker).read())

    finally:
      del os.environ['EMCC_LEAVE_INPUTS_RAW']
      self.emcc_args = emcc_args

  def test_fuzz(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('needs ta2')

    Building.COMPILER_TEST_OPTS += ['-I' + path_from_root('tests', 'fuzz')]

    def run_all(x):
      print x
      for name in glob.glob(path_from_root('tests', 'fuzz', '*.c')):
        print name
        self.do_run(open(path_from_root('tests', 'fuzz', name)).read(),
                    open(path_from_root('tests', 'fuzz', name + '.txt')).read(), force_c=True)

    run_all('normal')

    self.emcc_args += ['--llvm-lto', '1']

    run_all('lto')

  # Autodebug the code
  def do_autodebug(self, filename):
    output = Popen([PYTHON, AUTODEBUGGER, filename+'.o.ll', filename+'.o.ll.ll'], stdout=PIPE, stderr=self.stderr_redirect).communicate()[0]
    assert 'Success.' in output, output
    self.prep_ll_run(filename, filename+'.o.ll.ll', force_recompile=True) # rebuild .bc # TODO: use code in do_autodebug_post for this

  # Autodebug the code, after LLVM opts. Will only work once!
  def do_autodebug_post(self, filename):
    if not hasattr(self, 'post'):
      print 'Asking for post re-call'
      self.post = True
      return True
    print 'Autodebugging during post time'
    delattr(self, 'post')
    output = Popen([PYTHON, AUTODEBUGGER, filename+'.o.ll', filename+'.o.ll.ll'], stdout=PIPE, stderr=self.stderr_redirect).communicate()[0]
    assert 'Success.' in output, output
    shutil.copyfile(filename + '.o.ll.ll', filename + '.o.ll')
    Building.llvm_as(filename)
    Building.llvm_dis(filename)

  def test_autodebug(self):
    if Building.LLVM_OPTS: return self.skip('LLVM opts mess us up')
    Building.COMPILER_TEST_OPTS += ['--llvm-opts', '0']

    # Run a test that should work, generating some code
    self.test_structs()

    filename = os.path.join(self.get_dir(), 'src.cpp')
    self.do_autodebug(filename)

    # Compare to each other, and to expected output
    self.do_ll_run(path_from_root('tests', filename+'.o.ll.ll'), '''AD:-1,1''')
    assert open('stdout').read().startswith('AD:-1'), 'We must note when we enter functions'

    # Test using build_ll_hook
    src = '''
        #include <stdio.h>

        char cache[256], *next = cache;

        int main()
        {
          cache[10] = 25;
          next[20] = 51;
          int x = cache[10];
          double y = 11.52;
          printf("*%d,%d,%.2f*\\n", x, cache[20], y);
          return 0;
        }
      '''
    self.do_run(src, '''AD:-1,1''', build_ll_hook=self.do_autodebug)

  def test_corruption(self):
    if Settings.ASM_JS: return self.skip('cannot use corruption checks in asm')
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('needs ta2 for actual test')

    Settings.CORRUPTION_CHECK = 1

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>
      #include <string.h>
      int main(int argc, char **argv) {
        int size = 1024*argc;
        char *buffer = (char*)malloc(size);
      #if CORRUPT
        memset(buffer, argc, size+15);
      #else
        memset(buffer, argc, size);
      #endif
        for (int x = 0; x < size; x += argc*3) buffer[x] = x/3;
        int ret = 0;
        for (int x = 0; x < size; x++) ret += buffer[x];
        free(buffer);
        printf("All ok, %d\n", ret);
      }
    '''

    for corrupt in [1]:
      self.do_run(src.replace('CORRUPT', str(corrupt)), 'Heap corruption detected!' if corrupt else 'All ok, 4209')

  def test_corruption_2(self):
    if Settings.ASM_JS: return self.skip('cannot use corruption checks in asm')
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('needs ta2 for actual test')

    Settings.SAFE_HEAP = 1
    Settings.CORRUPTION_CHECK = 1

    # test for free(0), malloc(0), etc.
    src = r'''
      #include <iostream>
      #include <fstream>
      #include <stdlib.h>
      #include <stdio.h>

      void bye() {
        printf("all ok\n");
      }

      int main() {
        atexit(bye);

        std::string testPath = "/Script/WA-KA.txt";
        std::fstream str(testPath.c_str(), std::ios::in | std::ios::binary);

        if (str.is_open())
        {
          std::cout << "open!" << std::endl;
        } else {
          std::cout << "missing!" << std::endl;
        }

        return 1;
      }
      '''
    self.do_run(src, 'missing!\nall ok\n')

  def test_corruption_3(self):
    if Settings.ASM_JS: return self.skip('cannot use corruption checks in asm')
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip('needs ta2 for actual test')

    Settings.CORRUPTION_CHECK = 1

    # realloc
    src = r'''
      #include <stdlib.h>
      #include <stdio.h>
      #include <assert.h>

      void bye() {
        printf("all ok\n");
      }

      int main(int argc, char **argv) {
        atexit(bye);

        char *buffer = (char*)malloc(100);
        for (int i = 0; i < 100; i++) buffer[i] = (i*i)%256;
        buffer = (char*)realloc(buffer, argc + 50);
        for (int i = 0; i < argc + 50; i++) {
          //printf("%d : %d : %d : %d\n", i, (int)(buffer + i), buffer[i], (char)((i*i)%256));
          assert(buffer[i] == (char)((i*i)%256));
        }
        return 1;
      }
      '''
    self.do_run(src, 'all ok\n')

  ### Integration tests

  def test_ccall(self):
    if self.emcc_args is not None and '-O2' in self.emcc_args:
      self.emcc_args += ['--closure', '1'] # Use closure here, to test we export things right

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      extern "C" {
        int get_int() { return 5; }
        float get_float() { return 3.14; }
        char * get_string() { return "hello world"; }
        void print_int(int x) { printf("%d\n", x); }
        void print_float(float x) { printf("%.2f\n", x); }
        void print_string(char *x) { printf("%s\n", x); }
        int multi(int x, float y, int z, char *str) { if (x) puts(str); return (x+y)*z; }
        int * pointer(int *in) { printf("%d\n", *in); static int ret = 21; return &ret; }
      }

      int main(int argc, char **argv) {
        return 0;
      }
    '''

    post = '''
def process(filename):
  src = \'\'\'
    var Module = { 'noInitialRun': true };
    \'\'\' + open(filename, 'r').read() + \'\'\'
    Module.addOnExit(function () {
      Module.print('*');
      var ret;
      ret = Module['ccall']('get_int', 'number'); Module.print([typeof ret, ret]);
      ret = ccall('get_float', 'number'); Module.print([typeof ret, ret.toFixed(2)]);
      ret = ccall('get_string', 'string'); Module.print([typeof ret, ret]);
      ret = ccall('print_int', null, ['number'], [12]); Module.print(typeof ret);
      ret = ccall('print_float', null, ['number'], [14.56]); Module.print(typeof ret);
      ret = ccall('print_string', null, ['string'], ["cheez"]); Module.print(typeof ret);
      ret = ccall('print_string', null, ['array'], [[97, 114, 114, 45, 97, 121, 0]]); Module.print(typeof ret);
      ret = ccall('multi', 'number', ['number', 'number', 'number', 'string'], [2, 1.4, 3, 'more']); Module.print([typeof ret, ret]);
      var p = ccall('malloc', 'pointer', ['number'], [4]);
      setValue(p, 650, 'i32');
      ret = ccall('pointer', 'pointer', ['pointer'], [p]); Module.print([typeof ret, getValue(ret, 'i32')]);
      Module.print('*');
      // part 2: cwrap
      var multi = Module['cwrap']('multi', 'number', ['number', 'number', 'number', 'string']);
      Module.print(multi(2, 1.4, 3, 'atr'));
      Module.print(multi(8, 5.4, 4, 'bret'));
      Module.print('*');
      // part 3: avoid stack explosion
      for (var i = 0; i < TOTAL_STACK/60; i++) {
        ccall('multi', 'number', ['number', 'number', 'number', 'string'], [0, 0, 0, '123456789012345678901234567890123456789012345678901234567890']);
      }
      Module.print('stack is ok.');
    });
    Module.callMain();
  \'\'\'
  open(filename, 'w').write(src)
'''

    Settings.EXPORTED_FUNCTIONS += ['_get_int', '_get_float', '_get_string', '_print_int', '_print_float', '_print_string', '_multi', '_pointer', '_malloc']

    self.do_run(src, '*\nnumber,5\nnumber,3.14\nstring,hello world\n12\nundefined\n14.56\nundefined\ncheez\nundefined\narr-ay\nundefined\nmore\nnumber,10\n650\nnumber,21\n*\natr\n10\nbret\n53\n*\nstack is ok.\n', post_build=post)

  def test_pgo(self):
    if Settings.ASM_JS: return self.skip('PGO does not work in asm mode')

    def run_all(name, src):
      print name
      def test(expected, args=[], no_build=False):
        self.do_run(src, expected, args=args, no_build=no_build)
        return open(self.in_dir('src.cpp.o.js')).read()

      # Sanity check that it works and the dead function is emitted
      js = test('*9*')
      assert 'function _unused(' in js

      # Run with PGO, see that unused is true to its name
      Settings.PGO = 1
      test("*9*\n-s DEAD_FUNCTIONS='[\"_unused\"]'")
      Settings.PGO = 0

      # Kill off the dead function, still works and it is not emitted
      Settings.DEAD_FUNCTIONS = ['_unused']
      js = test('*9*')
      assert 'function _unused($' not in js # no compiled code
      assert 'function _unused(' in js # lib-generated stub
      Settings.DEAD_FUNCTIONS = []

      # Run the same code with argc that uses the dead function, see abort
      test(('dead function: unused'), args=['a', 'b'], no_build=True)

    # Normal stuff
    run_all('normal', r'''
      #include <stdio.h>
      extern "C" {
      int used(int x) {
        if (x == 0) return -1;
        return used(x/3) + used(x/17) + x%5;
      }
      int unused(int x) {
        if (x == 0) return -1;
        return unused(x/4) + unused(x/23) + x%7;
      }
      }
      int main(int argc, char **argv) {
        printf("*%d*\n", argc == 3 ? unused(argv[0][0] + 1024) : used(argc + 1555));
        return 0;
      }
    ''')

    # Call by function pointer
    run_all('function pointers', r'''
      #include <stdio.h>
      extern "C" {
      int used(int x) {
        if (x == 0) return -1;
        return used(x/3) + used(x/17) + x%5;
      }
      int unused(int x) {
        if (x == 0) return -1;
        return unused(x/4) + unused(x/23) + x%7;
      }
      }
      typedef int (*ii)(int);
      int main(int argc, char **argv) {
        ii pointers[256];
        for (int i = 0; i < 256; i++) {
          pointers[i] = (i == 3) ? unused : used;
        }
        printf("*%d*\n", pointers[argc](argc + 1555));
        return 0;
      }
    ''')

  def test_asm_pgo(self):
    if not Settings.ASM_JS: return self.skip('this is a test for PGO for asm (NB: not *in* asm)')

    src = open(path_from_root('tests', 'hello_libcxx.cpp')).read()
    output = 'hello, world!'

    self.do_run(src, output)
    shutil.move(self.in_dir('src.cpp.o.js'), self.in_dir('normal.js'))

    Settings.ASM_JS = 0
    Settings.PGO = 1
    self.do_run(src, output)
    Settings.ASM_JS = 1
    Settings.PGO = 0

    shutil.move(self.in_dir('src.cpp.o.js'), self.in_dir('pgo.js'))
    pgo_output = run_js(self.in_dir('pgo.js')).split('\n')[1]
    open('pgo_data.rsp', 'w').write(pgo_output)

    # with response file

    self.emcc_args += ['@pgo_data.rsp']
    self.do_run(src, output)
    self.emcc_args.pop()
    shutil.move(self.in_dir('src.cpp.o.js'), self.in_dir('pgoed.js'))

    before = len(open('normal.js').read())
    after = len(open('pgoed.js').read())
    assert after < 0.90 * before, [before, after] # expect a size reduction

    # with response in settings element itself

    open('dead_funcs', 'w').write(pgo_output[pgo_output.find('['):-1])
    self.emcc_args += ['-s', 'DEAD_FUNCTIONS=@' + self.in_dir('dead_funcs')]
    self.do_run(src, output)
    self.emcc_args.pop()
    self.emcc_args.pop()
    shutil.move(self.in_dir('src.cpp.o.js'), self.in_dir('pgoed2.js'))
    assert open('pgoed.js').read() == open('pgoed2.js').read()

    # with relative response in settings element itself

    open('dead_funcs', 'w').write(pgo_output[pgo_output.find('['):-1])
    self.emcc_args += ['-s', 'DEAD_FUNCTIONS=@dead_funcs']
    self.do_run(src, output)
    self.emcc_args.pop()
    self.emcc_args.pop()
    shutil.move(self.in_dir('src.cpp.o.js'), self.in_dir('pgoed2.js'))
    assert open('pgoed.js').read() == open('pgoed2.js').read()

  def test_exported_response(self):
    if self.emcc_args is None: return self.skip('requires emcc')

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      extern "C" {
        int other_function() { return 5; }
      }

      int main() {
        printf("waka!\n");
        return 0;
      }
    '''
    open('exps', 'w').write('["_main","_other_function"]')

    self.emcc_args += ['-s', 'EXPORTED_FUNCTIONS=@exps']
    self.do_run(src, '''waka!''')
    assert 'other_function' in open('src.cpp.o.js').read()

  def test_add_function(self):
    if self.emcc_args is None: return self.skip('requires emcc')

    Settings.INVOKE_RUN = 0
    Settings.RESERVED_FUNCTION_POINTERS = 1

    src = r'''
      #include <stdio.h>
      #include <stdlib.h>

      int main(int argc, char **argv) {
        int fp = atoi(argv[1]);
        printf("fp: %d\n", fp);
        void (*f)(int) = reinterpret_cast<void (*)(int)>(fp);
        f(7);
        return 0;
      }
    '''

    open(os.path.join(self.get_dir(), 'post.js'), 'w').write('''
      var newFuncPtr = Runtime.addFunction(function(num) {
        Module.print('Hello ' + num + ' from JS!');
      });
      Module.callMain([newFuncPtr.toString()]);
    ''')

    self.emcc_args += ['--post-js', 'post.js']
    self.do_run(src, '''Hello 7 from JS!''')

    if Settings.ASM_JS:
      Settings.RESERVED_FUNCTION_POINTERS = 0
      self.do_run(src, '''Finished up all reserved function pointers. Use a higher value for RESERVED_FUNCTION_POINTERS.''')
      generated = open('src.cpp.o.js').read()
      assert 'jsCall' not in generated
      Settings.RESERVED_FUNCTION_POINTERS = 1

      Settings.ALIASING_FUNCTION_POINTERS = 1 - Settings.ALIASING_FUNCTION_POINTERS # flip the test
      self.do_run(src, '''Hello 7 from JS!''')

  def test_demangle_stacks(self):
    if Settings.ASM_JS: return self.skip('spidermonkey has stack trace issues')

    src = r'''
      #include<stdio.h>
      #include<stdlib.h>

      namespace NameSpace {
        class Class {
        public:
          int Aborter(double x, char y, int *z) {
            int addr = x+y+(int)z;
            void *p = (void*)addr;
            for (int i = 0; i < 100; i++) free(p); // will abort, should show proper stack trace
          }
        };
      }

      int main(int argc, char **argv) {
        NameSpace::Class c;
        c.Aborter(1.234, 'a', NULL);
        return 0;
      }
    '''
    self.do_run(src, 'NameSpace::Class::Aborter(double, char, int*)');

  def test_embind(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    Building.COMPILER_TEST_OPTS += ['--bind']

    src = r'''
      #include<stdio.h>
      #include<emscripten/val.h>

      using namespace emscripten;

      int main() {
        val Math = val::global("Math");

        // two ways to call Math.abs
        printf("abs(-10): %d\n", Math.call<int>("abs", -10));
        printf("abs(-11): %d\n", Math["abs"](-11).as<int>());

        return 0;
      }
    '''
    self.do_run(src, 'abs(-10): 10\nabs(-11): 11');

  def test_embind_2(self):
    if self.emcc_args is None: return self.skip('requires emcc')
    Building.COMPILER_TEST_OPTS += ['--bind', '--post-js', 'post.js']
    open('post.js', 'w').write('''
      Module.print('lerp ' + Module.lerp(1, 2, 0.66) + '.');
    ''')
    src = r'''
      #include <stdio.h>
      #include <SDL/SDL.h>
      #include <emscripten/bind.h>
      using namespace emscripten;
      float lerp(float a, float b, float t) {
          return (1 - t) * a + t * b;
      }
      EMSCRIPTEN_BINDINGS(my_module) {
          function("lerp", &lerp);
      }
    '''
    self.do_run(src, 'lerp 1.66');

  def test_scriptaclass(self):
      if self.emcc_args is None: return self.skip('requires emcc')

      Settings.EXPORT_BINDINGS = 1

      header_filename = os.path.join(self.get_dir(), 'header.h')
      header = '''
        struct ScriptMe {
          int value;
          ScriptMe(int val);
          int getVal(); // XXX Sadly, inlining these will result in LLVM not
                        // producing any code for them (when just building
                        // as a library)
          void mulVal(int mul);
        };
      '''
      h = open(header_filename, 'w')
      h.write(header)
      h.close()

      src = '''
        #include "header.h"

        ScriptMe::ScriptMe(int val) : value(val) { }
        int ScriptMe::getVal() { return value; }
        void ScriptMe::mulVal(int mul) { value *= mul; }
      '''

      # Way 1: use demangler and namespacer

      script_src = '''
        var sme = Module._.ScriptMe.__new__(83);          // malloc(sizeof(ScriptMe)), ScriptMe::ScriptMe(sme, 83) / new ScriptMe(83) (at addr sme)
        Module._.ScriptMe.mulVal(sme, 2);                 // ScriptMe::mulVal(sme, 2)       sme.mulVal(2)
        Module.print('*' + Module._.ScriptMe.getVal(sme) + '*');
        _free(sme);
        Module.print('*ok*');
      '''
      post = '''
def process(filename):
  Popen([PYTHON, DEMANGLER, filename], stdout=open(filename + '.tmp', 'w')).communicate()
  Popen([PYTHON, NAMESPACER, filename, filename + '.tmp'], stdout=open(filename + '.tmp2', 'w')).communicate()
  src = open(filename, 'r').read().replace(
    '// {{MODULE_ADDITIONS}',
    'Module["_"] = ' + open(filename + '.tmp2', 'r').read().replace('var ModuleNames = ', '').rstrip() + ';\n\n' + script_src + '\n\n' +
      '// {{MODULE_ADDITIONS}'
  )
  open(filename, 'w').write(src)
'''
      # XXX disable due to possible v8 bug -- self.do_run(src, '*166*\n*ok*', post_build=post)

      if self.emcc_args is not None and '-O2' in self.emcc_args and 'ASM_JS=0' not in self.emcc_args: # without asm, closure minifies Math.imul badly
        self.emcc_args += ['--closure', '1'] # Use closure here, to test we export things right

      # Way 2: use CppHeaderParser

      Settings.RUNTIME_TYPE_INFO = 1

      header = '''
        #include <stdio.h>

        class Parent {
        protected:
          int value;
        public:
          Parent(int val);
          Parent(Parent *p, Parent *q); // overload constructor
          int getVal() { return value; }; // inline should work just fine here, unlike Way 1 before
          void mulVal(int mul);
        };

        class Child1 : public Parent {
        public:
          Child1() : Parent(7) { printf("Child1:%d\\n", value); };
          Child1(int val) : Parent(val*2) { value -= 1; printf("Child1:%d\\n", value); };
          int getValSqr() { return value*value; }
          int getValSqr(int more) { return value*value*more; }
          int getValTimes(int times=1) { return value*times; }
        };

        class Child2 : public Parent {
        public:
          Child2() : Parent(9) { printf("Child2:%d\\n", value); };
          int getValCube() { return value*value*value; }
          static void printStatic() { printf("*static*\\n"); }

          virtual void virtualFunc() { printf("*virtualf*\\n"); }
          virtual void virtualFunc2() { printf("*virtualf2*\\n"); }
          static void runVirtualFunc(Child2 *self) { self->virtualFunc(); };
        private:
          void doSomethingSecret() { printf("security breached!\\n"); }; // we should not be able to do this
        };
      '''
      open(header_filename, 'w').write(header)

      basename = os.path.join(self.get_dir(), 'bindingtest')
      output = Popen([PYTHON, BINDINGS_GENERATOR, basename, header_filename], stdout=PIPE, stderr=self.stderr_redirect).communicate()[0]
      #print output
      assert 'Traceback' not in output, 'Failure in binding generation: ' + output

      src = '''
        #include "header.h"

        Parent::Parent(int val) : value(val) { printf("Parent:%d\\n", val); }
        Parent::Parent(Parent *p, Parent *q) : value(p->value + q->value) { printf("Parent:%d\\n", value); }
        void Parent::mulVal(int mul) { value *= mul; }

        #include "bindingtest.cpp"
      '''

      post2 = '''
def process(filename):
  src = open(filename, 'a')
  src.write(open('bindingtest.js').read() + '\\n\\n')
  src.close()
'''

      def post3(filename):
        script_src_2 = '''
          var sme = new Module.Parent(42);
          sme.mulVal(2);
          Module.print('*')
          Module.print(sme.getVal());

          Module.print('c1');

          var c1 = new Module.Child1();
          Module.print(c1.getVal());
          c1.mulVal(2);
          Module.print(c1.getVal());
          Module.print(c1.getValSqr());
          Module.print(c1.getValSqr(3));
          Module.print(c1.getValTimes()); // default argument should be 1
          Module.print(c1.getValTimes(2));

          Module.print('c1 v2');

          c1 = new Module.Child1(8); // now with a parameter, we should handle the overloading automatically and properly and use constructor #2
          Module.print(c1.getVal());
          c1.mulVal(2);
          Module.print(c1.getVal());
          Module.print(c1.getValSqr());
          Module.print(c1.getValSqr(3));

          Module.print('c2')

          var c2 = new Module.Child2();
          Module.print(c2.getVal());
          c2.mulVal(2);
          Module.print(c2.getVal());
          Module.print(c2.getValCube());
          var succeeded;
          try {
            succeeded = 0;
            Module.print(c2.doSomethingSecret()); // should fail since private
            succeeded = 1;
          } catch(e) {}
          Module.print(succeeded);
          try {
            succeeded = 0;
            Module.print(c2.getValSqr()); // function from the other class
            succeeded = 1;
          } catch(e) {}
          Module.print(succeeded);
          try {
            succeeded = 0;
            c2.getValCube(); // sanity
            succeeded = 1;
          } catch(e) {}
          Module.print(succeeded);

          Module.Child2.prototype.printStatic(); // static calls go through the prototype

          // virtual function
          c2.virtualFunc();
          Module.Child2.prototype.runVirtualFunc(c2);
          c2.virtualFunc2();

          // extend the class from JS
          var c3 = new Module.Child2;
          Module.customizeVTable(c3, [{
            original: Module.Child2.prototype.virtualFunc,
            replacement: function() {
              Module.print('*js virtualf replacement*');
            }
          }, {
            original: Module.Child2.prototype.virtualFunc2,
            replacement: function() {
              Module.print('*js virtualf2 replacement*');
            }
          }]);
          c3.virtualFunc();
          Module.Child2.prototype.runVirtualFunc(c3);
          c3.virtualFunc2();

          c2.virtualFunc(); // original should remain the same
          Module.Child2.prototype.runVirtualFunc(c2);
          c2.virtualFunc2();
          Module.print('*ok*');
        '''
        code = open(filename).read()
        src = open(filename, 'w')
        src.write('var Module = {};\n') # name Module
        src.write(code)
        src.write(script_src_2 + '\n')
        src.close()

      Settings.RESERVED_FUNCTION_POINTERS = 20

      self.do_run(src, '''*
84
c1
Parent:7
Child1:7
7
14
196
588
14
28
c1 v2
Parent:16
Child1:15
15
30
900
2700
c2
Parent:9
Child2:9
9
18
5832
0
0
1
*static*
*virtualf*
*virtualf*
*virtualf2*''' + ('''
Parent:9
Child2:9
*js virtualf replacement*
*js virtualf replacement*
*js virtualf2 replacement*
*virtualf*
*virtualf*
*virtualf2*''') + '''
*ok*
''', post_build=(post2, post3))

  def test_scriptaclass_2(self):
      if self.emcc_args is None: return self.skip('requires emcc')

      Settings.EXPORT_BINDINGS = 1

      header_filename = os.path.join(self.get_dir(), 'header.h')
      header = '''
        #include <stdio.h>
        #include <string.h>

        class StringUser {
          char *s;
          int i;
        public:
          StringUser(char *string, int integer) : s(strdup(string)), i(integer) {}
          void Print(int anotherInteger, char *anotherString) {
            printf("|%s|%d|%s|%d|\\n", s, i, anotherString, anotherInteger);
          }
          void CallOther(StringUser *fr) { fr->Print(i, s); }
        };
      '''
      open(header_filename, 'w').write(header)

      basename = os.path.join(self.get_dir(), 'bindingtest')
      output = Popen([PYTHON, BINDINGS_GENERATOR, basename, header_filename], stdout=PIPE, stderr=self.stderr_redirect).communicate()[0]
      #print output
      assert 'Traceback' not in output, 'Failure in binding generation: ' + output

      src = '''
        #include "header.h"

        #include "bindingtest.cpp"
      '''

      post = '''
def process(filename):
  src = open(filename, 'a')
  src.write(open('bindingtest.js').read() + '\\n\\n')
  src.write(\'\'\'
          var user = new Module.StringUser("hello", 43);
          user.Print(41, "world");
            \'\'\')
  src.close()
'''
      self.do_run(src, '|hello|43|world|41|', post_build=post)

  def test_typeinfo(self):
    if self.emcc_args is not None and self.emcc_args != []: return self.skip('full LLVM opts optimize out all the code that uses the type')

    Settings.RUNTIME_TYPE_INFO = 1
    if Settings.QUANTUM_SIZE != 4: return self.skip('We assume normal sizes in the output here')

    src = '''
      #include<stdio.h>
      struct UserStruct {
        int x;
        char y;
        short z;
      };
      struct Encloser {
        short x;
        UserStruct us;
        int y;
      };
      int main() {
        Encloser e;
        e.us.y = 5;
        printf("*ok:%d*\\n", e.us.y);
        return 0;
      }
    '''

    post = '''
def process(filename):
  src = open(filename, 'r').read().replace(
    '// {{POST_RUN_ADDITIONS}}',
    \'\'\'
      if (Runtime.typeInfo) {
        Module.print('|' + Runtime.typeInfo.UserStruct.fields + '|' + Runtime.typeInfo.UserStruct.flatIndexes + '|');
        var t = Runtime.generateStructInfo(['x', { us: ['x', 'y', 'z'] }, 'y'], 'Encloser')
        Module.print('|' + [t.x, t.us.x, t.us.y, t.us.z, t.y] + '|');
        Module.print('|' + JSON.stringify(Runtime.generateStructInfo(['x', 'y', 'z'], 'UserStruct')) + '|');
      } else {
        Module.print('No type info.');
      }
    \'\'\'
  )
  open(filename, 'w').write(src)
'''

    self.do_run(src,
                 '*ok:5*\n|i32,i8,i16|0,4,6|\n|0,4,8,10,12|\n|{"__size__":8,"x":0,"y":4,"z":6}|',
                 post_build=post)

    # Make sure that without the setting, we don't spam the .js with the type info
    Settings.RUNTIME_TYPE_INFO = 0
    self.do_run(src, 'No type info.', post_build=post)

  ### Tests for tools

  def test_safe_heap(self):
    if not Settings.SAFE_HEAP: return self.skip('We need SAFE_HEAP to test SAFE_HEAP')
    if Settings.USE_TYPED_ARRAYS == 2: return self.skip('It is ok to violate the load-store assumption with TA2')
    if Building.LLVM_OPTS: return self.skip('LLVM can optimize away the intermediate |x|')

    src = '''
      #include<stdio.h>
      #include<stdlib.h>
      int main() { int *x = (int*)malloc(sizeof(int));
        *x = 20;
        float *y = (float*)x;
        printf("%f\\n", *y);
        printf("*ok*\\n");
        return 0;
      }
    '''

    try:
      self.do_run(src, '*nothingatall*')
    except Exception, e:
      # This test *should* fail, by throwing this exception
      assert 'Assertion failed: Load-store consistency assumption failure!' in str(e), str(e)

    # And we should not fail if we disable checking on that line

    Settings.SAFE_HEAP = 3
    Settings.SAFE_HEAP_LINES = ["src.cpp:7"]

    self.do_run(src, '*ok*')

    # But if we disable the wrong lines, we still fail

    Settings.SAFE_HEAP_LINES = ["src.cpp:99"]

    try:
      self.do_run(src, '*nothingatall*')
    except Exception, e:
      # This test *should* fail, by throwing this exception
      assert 'Assertion failed: Load-store consistency assumption failure!' in str(e), str(e)

    # And reverse the checks with = 2

    Settings.SAFE_HEAP = 2
    Settings.SAFE_HEAP_LINES = ["src.cpp:99"]

    self.do_run(src, '*ok*')

    Settings.SAFE_HEAP = 1

    # Linking multiple files should work too

    module = '''
      #include<stdio.h>
      #include<stdlib.h>
      void callFunc() { int *x = (int*)malloc(sizeof(int));
        *x = 20;
        float *y = (float*)x;
        printf("%f\\n", *y);
      }
    '''
    module_name = os.path.join(self.get_dir(), 'module.cpp')
    open(module_name, 'w').write(module)

    main = '''
      #include<stdio.h>
      #include<stdlib.h>
      extern void callFunc();
      int main() { callFunc();
        int *x = (int*)malloc(sizeof(int));
        *x = 20;
        float *y = (float*)x;
        printf("%f\\n", *y);
        printf("*ok*\\n");
        return 0;
      }
    '''
    main_name = os.path.join(self.get_dir(), 'main.cpp')
    open(main_name, 'w').write(main)

    Building.emcc(module_name, ['-g'])
    Building.emcc(main_name, ['-g'])
    all_name = os.path.join(self.get_dir(), 'all.bc')
    Building.link([module_name + '.o', main_name + '.o'], all_name)

    try:
      self.do_ll_run(all_name, '*nothingatall*')
    except Exception, e:
      # This test *should* fail, by throwing this exception
      assert 'Assertion failed: Load-store consistency assumption failure!' in str(e), str(e)

    # And we should not fail if we disable checking on those lines

    Settings.SAFE_HEAP = 3
    Settings.SAFE_HEAP_LINES = ["module.cpp:7", "main.cpp:9"]

    self.do_ll_run(all_name, '*ok*')

    # But we will fail if we do not disable exactly what we need to - any mistake leads to error

    for lines in [["module.cpp:22", "main.cpp:9"], ["module.cpp:7", "main.cpp:29"], ["module.cpp:127", "main.cpp:449"], ["module.cpp:7"], ["main.cpp:9"]]:
      Settings.SAFE_HEAP_LINES = lines
      try:
        self.do_ll_run(all_name, '*nothingatall*')
      except Exception, e:
        # This test *should* fail, by throwing this exception
        assert 'Assertion failed: Load-store consistency assumption failure!' in str(e), str(e)

  def test_debug(self):
    if '-g' not in Building.COMPILER_TEST_OPTS: Building.COMPILER_TEST_OPTS.append('-g')
    if self.emcc_args is not None:
      if '-O1' in self.emcc_args or '-O2' in self.emcc_args: return self.skip('optimizations remove LLVM debug info')

    src = '''
      #include <stdio.h>
      #include <assert.h>

      void checker(int x) {
        x += 20;
        assert(x < 15); // this is line 7!
      }

      int main() {
        checker(10);
        return 0;
      }
    '''
    try:
      self.do_run(src, '*nothingatall*')
    except Exception, e:
      # This test *should* fail
      assert 'Assertion failed: x < 15' in str(e), str(e)

    lines = open('src.cpp.o.js', 'r').readlines()
    lines = filter(lambda line: '___assert_fail(' in line or '___assert_func(' in line, lines)
    found_line_num = any(('//@line 7 "' in line) for line in lines)
    found_filename = any(('src.cpp"\n' in line) for line in lines)
    assert found_line_num, 'Must have debug info with the line number'
    assert found_filename, 'Must have debug info with the filename'

  def test_source_map(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip("doesn't pass without typed arrays")
    if NODE_JS not in JS_ENGINES: return self.skip('sourcemapper requires Node to run')
    if '-g' not in Building.COMPILER_TEST_OPTS: Building.COMPILER_TEST_OPTS.append('-g')

    src = '''
      #include <stdio.h>
      #include <assert.h>

      __attribute__((noinline)) int foo() {
        printf("hi"); // line 6
        return 1; // line 7
      }

      int main() {
        printf("%d", foo()); // line 11
        return 0; // line 12
      }
    '''

    dirname = self.get_dir()
    src_filename = os.path.join(dirname, 'src.cpp')
    out_filename = os.path.join(dirname, 'a.out.js')
    no_maps_filename = os.path.join(dirname, 'no-maps.out.js')

    with open(src_filename, 'w') as f: f.write(src)
    assert '-g4' not in Building.COMPILER_TEST_OPTS
    Building.emcc(src_filename, Settings.serialize() + self.emcc_args +
        Building.COMPILER_TEST_OPTS, out_filename)
    # the file name may find its way into the generated code, so make sure we
    # can do an apples-to-apples comparison by compiling with the same file name
    shutil.move(out_filename, no_maps_filename)
    with open(no_maps_filename) as f: no_maps_file = f.read()
    no_maps_file = re.sub(' *//@.*$', '', no_maps_file, flags=re.MULTILINE)
    Building.COMPILER_TEST_OPTS.append('-g4')

    def build_and_check():
      import json
      Building.emcc(src_filename, Settings.serialize() + self.emcc_args +
          Building.COMPILER_TEST_OPTS, out_filename, stderr=PIPE)
      with open(out_filename) as f: out_file = f.read()
      # after removing the @line and @sourceMappingURL comments, the build
      # result should be identical to the non-source-mapped debug version.
      # this is worth checking because the parser AST swaps strings for token
      # objects when generating source maps, so we want to make sure the
      # optimizer can deal with both types.
      out_file = re.sub(' *//@.*$', '', out_file, flags=re.MULTILINE)
      def clean(code):
        code = code.replace('{\n}', '{}')
        return '\n'.join(sorted(code.split('\n')))
      self.assertIdentical(clean(no_maps_file), clean(out_file))
      map_filename = out_filename + '.map'
      data = json.load(open(map_filename, 'r'))
      self.assertPathsIdentical(out_filename, data['file'])
      self.assertPathsIdentical(src_filename, data['sources'][0])
      self.assertTextDataIdentical(src, data['sourcesContent'][0])
      mappings = json.loads(jsrun.run_js(
        path_from_root('tools', 'source-maps', 'sourcemap2json.js'),
        tools.shared.NODE_JS, [map_filename]))
      seen_lines = set()
      for m in mappings:
        self.assertPathsIdentical(src_filename, m['source'])
        seen_lines.add(m['originalLine'])
      # ensure that all the 'meaningful' lines in the original code get mapped
      assert seen_lines.issuperset([6, 7, 11, 12])

    # EMCC_DEBUG=2 causes lots of intermediate files to be written, and so
    # serves as a stress test for source maps because it needs to correlate
    # line numbers across all those files.
    old_emcc_debug = os.environ.get('EMCC_DEBUG', None)
    os.environ.pop('EMCC_DEBUG', None)
    try:
      build_and_check()
      os.environ['EMCC_DEBUG'] = '2'
      build_and_check()
    finally:
      if old_emcc_debug is not None:
        os.environ['EMCC_DEBUG'] = old_emcc_debug
      else:
        os.environ.pop('EMCC_DEBUG', None)

  def test_exception_source_map(self):
    if Settings.USE_TYPED_ARRAYS != 2: return self.skip("doesn't pass without typed arrays")
    if '-g4' not in Building.COMPILER_TEST_OPTS: Building.COMPILER_TEST_OPTS.append('-g4')
    if NODE_JS not in JS_ENGINES: return self.skip('sourcemapper requires Node to run')

    src = '''
      #include <stdio.h>

      __attribute__((noinline)) void foo(int i) {
          if (i < 10) throw i; // line 5
      }

      int main() {
        int i;
        scanf("%d", &i);
        foo(i);
        return 0;
      }
    '''

    def post(filename):
      import json
      map_filename = filename + '.map'
      mappings = json.loads(jsrun.run_js(
        path_from_root('tools', 'source-maps', 'sourcemap2json.js'),
        tools.shared.NODE_JS, [map_filename]))
      with open(filename) as f: lines = f.readlines()
      for m in mappings:
        if m['originalLine'] == 5 and '__cxa_throw' in lines[m['generatedLine']]:
          return
      assert False, 'Must label throw statements with line numbers'

    dirname = self.get_dir()
    self.build(src, dirname, os.path.join(dirname, 'src.cpp'), post_build=(None, post))

  def test_linespecific(self):
    if Settings.ASM_JS: return self.skip('asm always has corrections on')

    if '-g' not in Building.COMPILER_TEST_OPTS: Building.COMPILER_TEST_OPTS.append('-g')
    if self.emcc_args:
      self.emcc_args += ['--llvm-opts', '0'] # llvm full opts make the expected failures here not happen
      Building.COMPILER_TEST_OPTS += ['--llvm-opts', '0']

    Settings.CHECK_SIGNS = 0
    Settings.CHECK_OVERFLOWS = 0

    # Signs

    src = '''
      #include <stdio.h>
      #include <assert.h>

      int main()
      {
        int varey = 100;
        unsigned int MAXEY = -1;
        printf("*%d*\\n", varey >= MAXEY); // 100 >= -1? not in unsigned!
      }
    '''

    Settings.CORRECT_SIGNS = 0
    self.do_run(src, '*1*') # This is a fail - we expect 0

    Settings.CORRECT_SIGNS = 1
    self.do_run(src, '*0*') # Now it will work properly

    # And now let's fix just that one line
    Settings.CORRECT_SIGNS = 2
    Settings.CORRECT_SIGNS_LINES = ["src.cpp:9"]
    self.do_run(src, '*0*')

    # Fixing the wrong line should not work
    Settings.CORRECT_SIGNS = 2
    Settings.CORRECT_SIGNS_LINES = ["src.cpp:3"]
    self.do_run(src, '*1*')

    # And reverse the checks with = 2
    Settings.CORRECT_SIGNS = 3
    Settings.CORRECT_SIGNS_LINES = ["src.cpp:3"]
    self.do_run(src, '*0*')
    Settings.CORRECT_SIGNS = 3
    Settings.CORRECT_SIGNS_LINES = ["src.cpp:9"]
    self.do_run(src, '*1*')

    Settings.CORRECT_SIGNS = 0

    # Overflows

    src = '''
      #include<stdio.h>
      int main() {
        int t = 77;
        for (int i = 0; i < 30; i++) {
          t = t + t + t + t + t + 1;
        }
        printf("*%d,%d*\\n", t, t & 127);
        return 0;
      }
    '''

    correct = '*186854335,63*'
    Settings.CORRECT_OVERFLOWS = 0
    try:
      self.do_run(src, correct)
      raise Exception('UNEXPECTED-PASS')
    except Exception, e:
      assert 'UNEXPECTED' not in str(e), str(e)
      assert 'Expected to find' in str(e), str(e)

    Settings.CORRECT_OVERFLOWS = 1
    self.do_run(src, correct) # Now it will work properly

    # And now let's fix just that one line
    Settings.CORRECT_OVERFLOWS = 2
    Settings.CORRECT_OVERFLOWS_LINES = ["src.cpp:6"]
    self.do_run(src, correct)

    # Fixing the wrong line should not work
    Settings.CORRECT_OVERFLOWS = 2
    Settings.CORRECT_OVERFLOWS_LINES = ["src.cpp:3"]
    try:
      self.do_run(src, correct)
      raise Exception('UNEXPECTED-PASS')
    except Exception, e:
      assert 'UNEXPECTED' not in str(e), str(e)
      assert 'Expected to find' in str(e), str(e)

    # And reverse the checks with = 2
    Settings.CORRECT_OVERFLOWS = 3
    Settings.CORRECT_OVERFLOWS_LINES = ["src.cpp:3"]
    self.do_run(src, correct)
    Settings.CORRECT_OVERFLOWS = 3
    Settings.CORRECT_OVERFLOWS_LINES = ["src.cpp:6"]
    try:
      self.do_run(src, correct)
      raise Exception('UNEXPECTED-PASS')
    except Exception, e:
      assert 'UNEXPECTED' not in str(e), str(e)
      assert 'Expected to find' in str(e), str(e)

    Settings.CORRECT_OVERFLOWS = 0

    # Roundings

    src = '''
      #include <stdio.h>
      #include <assert.h>

      int main()
      {
        TYPE x = -5;
        printf("*%d*", x/2);
        x = 5;
        printf("*%d*", x/2);

        float y = -5.33;
        x = y;
        printf("*%d*", x);
        y = 5.33;
        x = y;
        printf("*%d*", x);

        printf("\\n");
      }
    '''

    if Settings.USE_TYPED_ARRAYS != 2: # the errors here are very specific to non-i64 mode 1
      Settings.CORRECT_ROUNDINGS = 0
      self.do_run(src.replace('TYPE', 'long long'), '*-3**2**-6**5*') # JS floor operations, always to the negative. This is an undetected error here!
      self.do_run(src.replace('TYPE', 'int'), '*-2**2**-5**5*') # We get these right, since they are 32-bit and we can shortcut using the |0 trick
      self.do_run(src.replace('TYPE', 'unsigned int'), '*-2**2**-6**5*')

    Settings.CORRECT_ROUNDINGS = 1
    Settings.CORRECT_SIGNS = 1 # To be correct here, we need sign corrections as well
    self.do_run(src.replace('TYPE', 'long long'), '*-2**2**-5**5*') # Correct
    self.do_run(src.replace('TYPE', 'int'), '*-2**2**-5**5*') # Correct
    self.do_run(src.replace('TYPE', 'unsigned int'), '*2147483645**2**-5**5*') # Correct
    Settings.CORRECT_SIGNS = 0

    if Settings.USE_TYPED_ARRAYS != 2: # the errors here are very specific to non-i64 mode 1
      Settings.CORRECT_ROUNDINGS = 2
      Settings.CORRECT_ROUNDINGS_LINES = ["src.cpp:13"] # Fix just the last mistake
      self.do_run(src.replace('TYPE', 'long long'), '*-3**2**-5**5*')
      self.do_run(src.replace('TYPE', 'int'), '*-2**2**-5**5*') # Here we are lucky and also get the first one right
      self.do_run(src.replace('TYPE', 'unsigned int'), '*-2**2**-5**5*')

    # And reverse the check with = 2
    if Settings.USE_TYPED_ARRAYS != 2: # the errors here are very specific to non-i64 mode 1
      Settings.CORRECT_ROUNDINGS = 3
      Settings.CORRECT_ROUNDINGS_LINES = ["src.cpp:999"]
      self.do_run(src.replace('TYPE', 'long long'), '*-2**2**-5**5*')
      self.do_run(src.replace('TYPE', 'int'), '*-2**2**-5**5*')
      Settings.CORRECT_SIGNS = 1 # To be correct here, we need sign corrections as well
      self.do_run(src.replace('TYPE', 'unsigned int'), '*2147483645**2**-5**5*')
      Settings.CORRECT_SIGNS = 0

  def test_exit_status(self):
    if self.emcc_args is None: return self.skip('need emcc')
    src = r'''
      #include <stdio.h>
      #include <stdlib.h>
      static void cleanup() {
        printf("cleanup\n");
      }

      int main() {
        atexit(cleanup); // this atexit should still be called
        printf("hello, world!\n");
        exit(118); // Unusual exit status to make sure it's working!
      }
    '''
    open('post.js', 'w').write('''
      Module.addOnExit(function () {
        Module.print('I see exit status: ' + EXITSTATUS);
      });
      Module.callMain();
    ''')
    self.emcc_args += ['-s', 'INVOKE_RUN=0', '--post-js', 'post.js']
    self.do_run(src, 'hello, world!\ncleanup\nI see exit status: 118')

  def test_gc(self):
    if self.emcc_args == None: return self.skip('needs ta2')
    if Settings.ASM_JS: return self.skip('asm cannot support generic function table')

    Settings.GC_SUPPORT = 1

    src = r'''
      #include <stdio.h>
      #include <gc.h>
      #include <assert.h>

      void *global;

      void finalizer(void *ptr, void *arg) {
        printf("finalizing %d (global == %d)\n", (int)arg, ptr == global);
      }

      void finalizer2(void *ptr, void *arg) {
        printf("finalizing2 %d (global == %d)\n", (int)arg, ptr == global);
      }

      int main() {
        GC_INIT();

        void *local, *local2, *local3, *local4, *local5, *local6;

        // Hold on to global, drop locals

        global = GC_MALLOC(1024); // rooted since in a static allocation
        GC_REGISTER_FINALIZER_NO_ORDER(global, finalizer, 0, 0, 0);
        printf("alloc %p\n", global);

        local = GC_MALLOC(1024); // not rooted since stack is not scanned
        GC_REGISTER_FINALIZER_NO_ORDER(local, finalizer, (void*)1, 0, 0);
        printf("alloc %p\n", local);

        assert((char*)local - (char*)global >= 1024 || (char*)global - (char*)local >= 1024);

        local2 = GC_MALLOC(1024); // no finalizer
        printf("alloc %p\n", local2);

        local3 = GC_MALLOC(1024); // with finalizable2
        GC_REGISTER_FINALIZER_NO_ORDER(local3, finalizer2, (void*)2, 0, 0);
        printf("alloc %p\n", local);

        local4 = GC_MALLOC(1024); // yet another
        GC_REGISTER_FINALIZER_NO_ORDER(local4, finalizer2, (void*)3, 0, 0);
        printf("alloc %p\n", local);

        printf("basic test\n");

        GC_FORCE_COLLECT();

        printf("*\n");

        GC_FREE(global); // force free will actually work

        // scanning inside objects

        global = GC_MALLOC(12);
        GC_REGISTER_FINALIZER_NO_ORDER(global, finalizer, 0, 0, 0);
        local = GC_MALLOC(12);
        GC_REGISTER_FINALIZER_NO_ORDER(local, finalizer, (void*)1, 0, 0);
        local2 = GC_MALLOC_ATOMIC(12);
        GC_REGISTER_FINALIZER_NO_ORDER(local2, finalizer, (void*)2, 0, 0);
        local3 = GC_MALLOC(12);
        GC_REGISTER_FINALIZER_NO_ORDER(local3, finalizer, (void*)3, 0, 0);
        local4 = GC_MALLOC(12);
        GC_REGISTER_FINALIZER_NO_ORDER(local4, finalizer, (void*)4, 0, 0);
        local5 = GC_MALLOC_UNCOLLECTABLE(12);
        // This should never trigger since local5 is uncollectable
        GC_REGISTER_FINALIZER_NO_ORDER(local5, finalizer, (void*)5, 0, 0);

        printf("heap size = %d\n", GC_get_heap_size());

        local4 = GC_REALLOC(local4, 24);

        printf("heap size = %d\n", GC_get_heap_size());

        local6 = GC_MALLOC(12);
        GC_REGISTER_FINALIZER_NO_ORDER(local6, finalizer, (void*)6, 0, 0);
        // This should be the same as a free
        GC_REALLOC(local6, 0);

        void **globalData = (void**)global;
        globalData[0] = local;
        globalData[1] = local2;

        void **localData = (void**)local;
        localData[0] = local3;

        void **local2Data = (void**)local2;
        local2Data[0] = local4; // actually ignored, because local2 is atomic, so 4 is freeable

        printf("object scan test test\n");

        GC_FORCE_COLLECT();

        printf("*\n");

        GC_FREE(global); // force free will actually work

        printf("*\n");

        GC_FORCE_COLLECT();

        printf(".\n");

        global = 0;

        return 0;
      }
    '''
    self.do_run(src, '''basic test
finalizing 1 (global == 0)
finalizing2 2 (global == 0)
finalizing2 3 (global == 0)
*
finalizing 0 (global == 1)
heap size = 72
heap size = 84
finalizing 6 (global == 0)
object scan test test
finalizing 4 (global == 0)
*
finalizing 0 (global == 1)
*
finalizing 1 (global == 0)
finalizing 2 (global == 0)
finalizing 3 (global == 0)
.
''')

# Generate tests for everything
def make_run(fullname, name=-1, compiler=-1, embetter=0, quantum_size=0,
    typed_arrays=0, emcc_args=None, env=None):

  if env is None: env = {}

  TT = type(fullname, (T,), dict(run_name = fullname, env = env))

  def tearDown(self):
    super(TT, self).tearDown()

    for k, v in self.env.iteritems():
      del os.environ[k]

    # clear global changes to Building
    Building.COMPILER_TEST_OPTS = []
    Building.COMPILER = CLANG
    Building.LLVM_OPTS = 0

  TT.tearDown = tearDown

  def setUp(self):
    super(TT, self).setUp()
    for k, v in self.env.iteritems():
      assert k not in os.environ, k + ' should not be in environment'
      os.environ[k] = v

    global checked_sanity
    if not checked_sanity:
      print '(checking sanity from test runner)' # do this after we set env stuff
      check_sanity(force=True)
      checked_sanity = True

    Building.COMPILER_TEST_OPTS = ['-g']
    os.chdir(self.get_dir()) # Ensure the directory exists and go there
    Building.COMPILER = compiler

    self.emcc_args = None if emcc_args is None else emcc_args[:]
    if self.emcc_args is not None:
      Settings.load(self.emcc_args)
      Building.LLVM_OPTS = 0
      if '-O2' in self.emcc_args:
        Building.COMPILER_TEST_OPTS = [] # remove -g in -O2 tests, for more coverage
      #Building.COMPILER_TEST_OPTS += self.emcc_args
      for arg in self.emcc_args:
        if arg.startswith('-O'):
          Building.COMPILER_TEST_OPTS.append(arg) # so bitcode is optimized too, this is for cpp to ll
        else:
          try:
            key, value = arg.split('=')
            Settings[key] = value # forward  -s K=V
          except:
            pass
      return

    # TODO: Move much of these to a init() function in shared.py, and reuse that
    Settings.USE_TYPED_ARRAYS = typed_arrays
    Settings.INVOKE_RUN = 1
    Settings.RELOOP = 0 # we only do them in the "o2" pass
    Settings.MICRO_OPTS = embetter
    Settings.QUANTUM_SIZE = quantum_size
    Settings.ASSERTIONS = 1-embetter
    Settings.SAFE_HEAP = 1-embetter
    Settings.CHECK_OVERFLOWS = 1-embetter
    Settings.CORRECT_OVERFLOWS = 1-embetter
    Settings.CORRECT_SIGNS = 0
    Settings.CORRECT_ROUNDINGS = 0
    Settings.CORRECT_OVERFLOWS_LINES = CORRECT_SIGNS_LINES = CORRECT_ROUNDINGS_LINES = SAFE_HEAP_LINES = []
    Settings.CHECK_SIGNS = 0 #1-embetter
    Settings.RUNTIME_TYPE_INFO = 0
    Settings.DISABLE_EXCEPTION_CATCHING = 0
    Settings.INCLUDE_FULL_LIBRARY = 0
    Settings.BUILD_AS_SHARED_LIB = 0
    Settings.RUNTIME_LINKED_LIBS = []
    Settings.EMULATE_UNALIGNED_ACCESSES = int(Settings.USE_TYPED_ARRAYS == 2 and Building.LLVM_OPTS == 2)
    Settings.DOUBLE_MODE = 1 if Settings.USE_TYPED_ARRAYS and Building.LLVM_OPTS == 0 else 0
    Settings.PRECISE_I64_MATH = 0
    Settings.NAMED_GLOBALS = 0 if not embetter else 1

  TT.setUp = setUp

  return TT

# Make one run with the defaults
default = make_run("default", compiler=CLANG, emcc_args=[])

# Make one run with -O1, with safe heap
o1 = make_run("o1", compiler=CLANG, emcc_args=["-O1", "-s", "ASM_JS=0", "-s", "SAFE_HEAP=1"])

# Make one run with -O2, but without closure (we enable closure in specific tests, otherwise on everything it is too slow)
o2 = make_run("o2", compiler=CLANG, emcc_args=["-O2", "-s", "ASM_JS=0", "-s", "JS_CHUNK_SIZE=1024"])

# asm.js
asm1 = make_run("asm1", compiler=CLANG, emcc_args=["-O1"])
asm2 = make_run("asm2", compiler=CLANG, emcc_args=["-O2"])
asm2f = make_run("asm2f", compiler=CLANG, emcc_args=["-O2", "-s", "PRECISE_F32=1"])
asm2g = make_run("asm2g", compiler=CLANG, emcc_args=["-O2", "-g", "-s", "ASSERTIONS=1", "--memory-init-file", "1", "-s", "CHECK_HEAP_ALIGN=1"])
asm2x86 = make_run("asm2x86", compiler=CLANG, emcc_args=["-O2", "-g", "-s", "CHECK_HEAP_ALIGN=1"], env={"EMCC_LLVM_TARGET": "i386-pc-linux-gnu"})

# Make custom runs with various options
for compiler, quantum, embetter, typed_arrays in [
  (CLANG, 4, 0, 0),
  (CLANG, 4, 1, 1),
]:
  fullname = 's_0_%d%s%s' % (
    embetter, '' if quantum == 4 else '_q' + str(quantum), '' if typed_arrays in [0, 1] else '_t' + str(typed_arrays)
  )
  locals()[fullname] = make_run(fullname, fullname, compiler, embetter, quantum, typed_arrays)

del T # T is just a shape for the specific subclasses, we don't test it itself
