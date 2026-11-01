#include "randomx.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct T {const char* key; const char* input; const char* want;};
static const struct T tests[]={
{"test key 000","This is a test","639183aae1bf4c9a35884cb46b09cad9175f04efd7684e7262a0ac1c2f0b4e3f"},
{"test key 000","Lorem ipsum dolor sit amet","300a0adb47603dedb42228ccb2b211104f4da45af709cd7547cd049e9489c969"},
{"test key 000","sed do eiusmod tempor incididunt ut labore et dolore magna aliqua","c36d4ed4191e617309867ed66a443be4075014e2b061bcdaf9ce7b721d2b77a8"},
{"test key 001","sed do eiusmod tempor incididunt ut labore et dolore magna aliqua","e9ff4503201c0c2cca26d285c93ae883f9b1d30c9eb240b820756f2d5a7905fc"}};
int main(void) {
  randomx_cache* cache=randomx_alloc_cache(RANDOMX_FLAG_DEFAULT);
  if(!cache){fputs("ERROR CACHE\n",stderr);return 2;}
  char previous[100]=""; unsigned okcount=0;
  for(unsigned i=0;i<sizeof(tests)/sizeof(tests[0]);i++){
    if(strcmp(previous,tests[i].key)){randomx_init_cache(cache,tests[i].key,strlen(tests[i].key));strcpy(previous,tests[i].key);}
    randomx_vm* vm=randomx_create_vm(RANDOMX_FLAG_DEFAULT,cache,NULL);
    if(!vm){fputs("ERROR VM\n",stderr);return 3;}
    unsigned char hash[RANDOMX_HASH_SIZE];char hex[RANDOMX_HASH_SIZE*2+1];
    randomx_calculate_hash(vm,tests[i].input,strlen(tests[i].input),hash);
    randomx_destroy_vm(vm);
    for(unsigned j=0;j<RANDOMX_HASH_SIZE;j++)sprintf(hex+2*j,"%02x",hash[j]);
    hex[RANDOMX_HASH_SIZE*2]=0;
    int ok=!strcmp(hex,tests[i].want);
    printf("TEST %u %s\nEXPECTED %s\nACTUAL   %s\n",i+1,ok?"PASS":"FAIL",tests[i].want,hex);
    if(ok)okcount++;
  }
  randomx_release_cache(cache);
  printf("OFFICIAL_RANDOMX_V1: %u/%zu PASS\n",okcount,sizeof(tests)/sizeof(tests[0]));
  return okcount==sizeof(tests)/sizeof(tests[0])?0:1;
}
