# NEXİS-RX LAB26 — Gerçek RandomX içinde gereksiz bellek yazmalarının kaldırılması

## Özet
Tarihsel Monero bloğu 3300100'ün iki gerçek nonce'u üzerinde resmî RandomX v1.2.1 light VM'ye bütün scratchpad okuma/yazmalarını takip eden bir kayıt eklendi. İlk çalıştırmada **sonraki bir okumadan önce üzerine yazılan** ve hiç okunmayan **tam yazma işlemleri** belirlendi. İkinci çalıştırmada bu yazmalar gerçekten atlandı. Son 256 bitlik hash resmî RandomX ile birebir karşılaştırıldı.

## Kanıtlanmış gerçek sonuç
| Ölçüm | Kazanan nonce 1079945234 | Komşu nonce 1079945235 | Toplam |
|---|---:|---:|---:|
| Dinamik scratchpad yazma işlemi | 442.897 | 488.163 | 931.060 |
| Hiç okunmadan tamamen üzerine yazılmış işlem | 63.640 | 91.922 | 155.562 |
| Silinebilen yazma baytı | 514.640 | 741.568 | 1.256.208 |
| Resmî RandomX 256-bit hash ile birebir eşleşme | Evet | Evet | 2/2 |
| Gereksiz yazma oranı | %14,37 | %18,83 | %16,708 |

Toplam 8.497.056 bayt yazma işleminden 1.256.208 baytı atlandı (%14,784).

## Yöntem sınırları
- İzlenen olaylar bytecode içindeki tüm scratchpad okumaları ve ISTORE yazmaları, VM döngüsündeki integer/floating point scratchpad okuma ve yazmalarıdır.
- Son AES scratchpad indirgemesinin tüm 2 MiB belleği okuduğu hesaba katılmıştır. Bu sayede son aşamadaki canlı yazmalar yanlışlıkla silinmez.
- Kayıt, hangi yazmanın ileride okunmadığını **tam koşu sonunda** belirler. İkinci koşu bu listeden sadece güvenli görülenleri siler.
- Dolayısıyla bu çalışma **önceden bilinen tüm nonce'larda uygulanabilen canlı bir optimizasyon değildir**: önceden yapılan tam yürütmenin maliyetini ödememiz gerekir.
- Bu raporda H/s performans artışı iddia edilmez; her iki modda da izleme maliyeti vardır ve adil kontrol/işlem kıyası yapılmamıştır.
- Bu sonuç yalnız 2 nonce için doğrulanmış, genelleştirilmiş matematiksel eleme teoremi değildir.
- Bir sonraki araştırmada istenen, geleceği bilmeden yazma birleştirebilen ve veriyi okunmadan önce doğru taşıyan bir **çalışma zamanı yazma erteleme** stratejisi kurmak ve hem hash hem H/s karşılaştırmaktır.
- Düşük zorluklu share denemesi ve ağ bloğu kazanma iddiası yoktur.

## Kaynak
- Başarılı deney: https://github.com/byhicc-sudo/test/actions/runs/41379688071
- İzleme ve replay C++: https://github.com/byhicc-sudo/test/blob/nexis-rx-lab26-dead-store-20261102/nexis_rx_hist100/lab26_dead_store.cpp
- Kaynak koda yapılan izleme noktaları: https://github.com/byhicc-sudo/test/blob/nexis-rx-lab26-dead-store-20261102/nexis_rx_hist100/lab26_patch_official.py
- Resmî deney çıktısı: https://github.com/byhicc-sudo/test/actions/runs/41379688071/artifacts/13112756035
