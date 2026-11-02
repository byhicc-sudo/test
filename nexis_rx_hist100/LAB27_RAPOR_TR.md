# NEXİS-RX LAB27 — Canlı ISTORE yazma birleştirme testi

## Hedef
LAB26'da ilk tam hesap sonrası elde edilen dinamik ölü yazma listesini kullanmadan, hesaplama sırasında güvenli yazma birleştirme denemek. Bütün geçerli 256-bit RandomX hash çıktıları korunmalı; gerçek CPU hızı ölçülmeli.

## Deney
- Sabit gerçek tarihsel Monero bloğu: 3300100
- Gerçek kazanan nonce: 1079945234 (referans hash kontrolü)
- 16 ardışık nonce için 2 normal + 2 ertelenmiş koşu: 64 tam hash
- Kontrol: RandomX v1.2.1 sabit resmî kaynak/commit 102f8acf90a7649ada410de5499a7ec62e49e1da
- *ISTORE* yazmaları çalışma sırasında küçük bekleyen yazma listesine alınır.
- Aynı adrese yeni yazma gelirse ilk bekleyen yazma fiziksel belleğe yapılmadan değiştirilir. Bellekten okuma gerekiyorsa bekleyen ilgili değer önce belleğe yazılır. Her VM bytecode iterasyonu sonunda bütün bekleyen yazmalar ana belleğe aktarılır. Böylece yazma sırası semantiği korunur.
- 4 test turunda çıktılar 64/64 resmî RandomX referansıyla tam eşleşmiştir.

## Gerçek sonuçlar
| Ölçüm | Normal mod | Canlı erteleme |
|---|---:|---:|
| Kıyaslama hash sayısı | 32 | 32 |
| Program içi ISTORE denemesi | 8.265.280 | 8.265.280 |
| Fiziksel ISTORE yazması | 8.265.280 | 8.241.932 |
| Birleştirilmiş yazma | 0 | 23.348 |
| Birleştirilen işlem yüzdesi | 0 | %0,282483 |
| Gerçek RandomX hızı | 5,651004 H/s | 5,120533 H/s |
| Hız oranı, yeni / normal | 1,00 | 0,906128 |
| Net hız değişimi | — | **-%9,3872** |

- Bellek okuması öncesi yapılan gecikmiş yazmalar: 37.678.
- İterasyon sonunda yapılan gecikmiş yazmalar: 8.204.254.
- Normal ve yeni yöntemde aynı instrumented RandomX kütüphanesi kullanılmıştır. Bu nedenle ölçüm, instrumentasyonun sabit maliyetine rağmen ertelenmiş yazma yönetiminin ek yükünü gösterir.
- Tam resmî, hiç değiştirilmemiş C++ kaynak koduyla karşılıklı bağımsız H/s kıyası yapılmadığı için bu yalnız bu iki deneme modunun iç karşılaştırmasıdır.

## Sonuç
LAB26'da %16,71 **dinamik gereksiz yazma** bulunması bir keşiftir, ancak bu oran yalnız tam koşudan sonra elde edilir; doğrudan madencilik kazancı değildir. LAB27'de geleceği bilmeden çalışma zamanında %0,28 ISTORE fiziksel yazması kaldırıldı ve hız %9,39 düştü. Bu, 5000× algoritmik kestirme hedefine yaklaşan bir hızlanma değildir.

## Araştırma kararı
LAB27'nin bu sürümünü performans yönünden reddediyoruz. Sonraki araştırma ancak statik derleme anında kanıtlanabilen ölü register komutları, matematiksel işlem eşdeğerlikleri veya genel geçerli erken ret koşulları üzerinden ilerlemeli. Her deneme referans tam RandomX hash'i ve net CPU maliyetiyle kıyaslanmalı.

## Kaynaklar
- Laboratuvar: https://github.com/byhicc-sudo/test/actions/runs/41379990669
- 64 gerçek deneme CSV ve sonuçları: https://github.com/byhicc-sudo/test/actions/runs/41379990669/artifacts/13112732588
- C++: https://github.com/byhicc-sudo/test/blob/nexis-rx-lab27-online-writeback-20261102/nexis_rx_hist100/lab27_online_writeback.cpp
- Resmî RandomX C++'a uygulanan kontrollü patch: https://github.com/byhicc-sudo/test/blob/nexis-rx-lab27-online-writeback-20261102/nexis_rx_hist100/lab27_patch_official.py
