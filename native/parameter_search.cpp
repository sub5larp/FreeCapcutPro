// Fixed-message SHA-256 search for parameters constrained by the selected file.
// SSE2 is part of the Windows x64 baseline; no CPU-specific extensions are used.
// No CRT is needed: suppress optional aligned-allocation declarations.
#define _INC_MALLOC
#include <emmintrin.h>
extern "C" long _InterlockedCompareExchange(long volatile*, long, long);
extern "C" long _InterlockedExchange(long volatile*, long);
extern "C" long _InterlockedExchangeAdd(long volatile*, long);
#pragma intrinsic(_InterlockedCompareExchange, _InterlockedExchange, _InterlockedExchangeAdd)
typedef unsigned char uint8_t;
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
typedef long LONG;
typedef void* HANDLE;
extern "C" __declspec(dllimport) uint64_t __stdcall GetTickCount64();
extern "C" __declspec(dllimport) unsigned long __stdcall GetActiveProcessorCount(unsigned short);
extern "C" __declspec(dllimport) HANDLE __stdcall CreateThread(void*, unsigned long long, unsigned long (__stdcall*)(void*), void*, unsigned long, unsigned long*);
extern "C" __declspec(dllimport) unsigned long __stdcall WaitForSingleObject(HANDLE, unsigned long);
extern "C" __declspec(dllimport) int __stdcall CloseHandle(HANDLE);

static const uint32_t K[64] = {
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};
static const uint32_t IV[8] = {0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
using V = __m128i;
static inline V add(V a,V b){return _mm_add_epi32(a,b);}
static inline V xr(V a,V b){return _mm_xor_si128(a,b);}
template<int N> static inline V rr(V x){return _mm_or_si128(_mm_srli_epi32(x,N),_mm_slli_epi32(x,32-N));}
static inline V spl(uint32_t v){return _mm_set1_epi32(static_cast<int>(v));}

static int matches(uint32_t step,uint32_t length,uint8_t key,const uint32_t* target){
  V w[64];
  for(int i=0;i<16;i++)w[i]=_mm_setzero_si128();
  w[0]=spl(step);w[1]=_mm_set_epi32(length+3,length+2,length+1,length);
  w[2]=spl((uint32_t(key)<<24)|0x00800000);w[15]=spl(72);
  for(int i=16;i<64;i++){
    V s0=xr(xr(rr<7>(w[i-15]),rr<18>(w[i-15])),_mm_srli_epi32(w[i-15],3));
    V s1=xr(xr(rr<17>(w[i-2]),rr<19>(w[i-2])),_mm_srli_epi32(w[i-2],10));
    w[i]=add(add(w[i-16],s0),add(w[i-7],s1));
  }
  V a=spl(IV[0]),b=spl(IV[1]),c=spl(IV[2]),d=spl(IV[3]);
  V e=spl(IV[4]),f=spl(IV[5]),g=spl(IV[6]),h=spl(IV[7]);
  for(int i=0;i<64;i++){
    V s1=xr(xr(rr<6>(e),rr<11>(e)),rr<25>(e));
    V ch=xr(_mm_and_si128(e,f),_mm_andnot_si128(e,g));
    V t1=add(add(add(h,s1),add(ch,spl(K[i]))),w[i]);
    V s0=xr(xr(rr<2>(a),rr<13>(a)),rr<22>(a));
    V maj=xr(xr(_mm_and_si128(a,b),_mm_and_si128(a,c)),_mm_and_si128(b,c));
    V t2=add(s0,maj);
    h=g;g=f;f=e;e=add(d,t1);d=c;c=b;b=a;a=add(t1,t2);
  }
  V states[8]={a,b,c,d,e,f,g,h};
  V equal=_mm_set1_epi32(-1);
  for(int i=0;i<8;i++)equal=_mm_and_si128(equal,_mm_cmpeq_epi32(states[i],spl(target[i]-IV[i])));
  return _mm_movemask_ps(_mm_castsi128_ps(equal));
}

struct Search {
  uint8_t key;
  const uint32_t* target;
  const uint64_t* positions;
  const uint8_t* encrypted;
  uint32_t count,last;
  uint64_t deadline;
  volatile LONG *cancel;
  volatile LONG next,found,timed_out;
  uint32_t* result;
};
static bool stopped(Search* s){
  if(_InterlockedCompareExchange(&s->found,0,0)||_InterlockedCompareExchange(s->cancel,0,0))return true;
  if(GetTickCount64()>s->deadline){_InterlockedExchange(&s->timed_out,1);return true;}
  return false;
}
static unsigned long __stdcall worker(void* context){
  Search* s=static_cast<Search*>(context);
  while(!stopped(s)){
    uint32_t step=static_cast<uint32_t>(_InterlockedExchangeAdd(&s->next,1));
    if(step>s->last)return 0;
    uint32_t low=1,high=step;
    for(uint32_t i=0;i<s->count&&low<=high;i++){
      uint32_t remainder=static_cast<uint32_t>(s->positions[i]%step);
      if(s->encrypted[i]){if(remainder+1>low)low=remainder+1;}
      else if(remainder<high)high=remainder;
    }
    for(uint32_t length=low;length<=high;length+=4){
      if(((length-low)&8191)==0&&stopped(s))return 0;
      int mask=matches(step,length,s->key,s->target);
      for(int lane=0;lane<4;lane++)if((mask&(1<<lane))&&length+lane<=high){
        if(_InterlockedCompareExchange(&s->found,1,0)==0){s->result[0]=step;s->result[1]=length+lane;}
        return 0;
      }
    }
  }
  return 0;
}
extern "C" __declspec(dllexport) int search_parameters(
  uint8_t key,const uint32_t* target,const uint64_t* positions,const uint8_t* encrypted,
  uint32_t count,uint32_t first,uint32_t last,uint32_t timeout_ms,
  volatile LONG* cancel,uint32_t* result){
  if(!count||!first||last<first||last>5000000)return 1;
  Search s;
  s.key=key;s.target=target;s.positions=positions;s.encrypted=encrypted;s.count=count;s.last=last;
  s.deadline=GetTickCount64()+timeout_ms;s.cancel=cancel;s.result=result;
  s.next=first;s.found=0;s.timed_out=0;
  HANDLE workers[16];
  unsigned long n=GetActiveProcessorCount(0xffff);
  if(n<1)n=1;if(n>16)n=16;
  for(unsigned long i=0;i<n;i++)workers[i]=CreateThread(nullptr,0,worker,&s,0,nullptr);
  worker(&s);
  for(unsigned long i=0;i<n;i++)if(workers[i]){WaitForSingleObject(workers[i],0xffffffff);CloseHandle(workers[i]);}
  if(s.found)return 0;
  if(_InterlockedCompareExchange(cancel,0,0))return 3;
  return s.timed_out?2:1;
}
