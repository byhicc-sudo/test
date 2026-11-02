# NEXİS-RX LAB24 — Tam RandomX 561-nonce GF(2) duyarlılık analizi

## Ölçüm tarihi
2 Kasım 2026, TSİ (GitHub Actions çalışması 2026-11-02 00:10 UTC civarı sonuçlandı).

## Gerçek veri
- Monero tarihsel blok yüksekliği: 3300100
- Gerçek blok zorluğu: 367410898587
- Gerçek kazanan nonce: 1079945234 (yalnız doğrulama için)
- Deneyde kullanılan, kazanan nonce'dan bağımsız başlangıç nonce'u: 1924096911
- Hash motoru: resmî RandomX, doğrulanmış sabit commit 102f8acf90a7649ada410de5499a7ec62e49e1da
- Gerçek tam RandomX hesapları: 561 farklı nonce
- Deney karmaşıklığı: 1 ana nonce + 32 tek bit + 496 iki bit + 32 üç bit

## Sonuçlar
| Metrik | Sonuç |
|---|---|
| Başlangıç BLAKE2b 512-bit için 32-bit nonce GF(2) rank | 32/32 |
| Tam RandomX 256-bit için 32-bit nonce GF(2) rank | 32/32 |
| Ağ hedefi için önemli en yüksek 38 bit için GF(2) rank | 32/32 |
| Çift bit farkı, BLAKE2b başlangıcında sıfır olmayan | 496/496 |
| Çift bit farkı, tam RandomX'te sıfır olmayan | 496/496 |
| Çift bit farkı, hedefin yüksek 38 bitinde sıfır olmayan | 496/496 |
| Üç bit farkı, BLAKE2b başlangıcında sıfır olmayan | 32/32 |
| Üç bit farkı, tam RandomX'te sıfır olmayan | 32/32 |
| Üç bit farkı, hedefin yüksek 38 bitinde sıfır olmayan | 32/32 |
| Gerçek ağ zorluğunda bulunan yeni blok | 0 |
| Ölçülen süre | 104,144952 saniye |
| Referans light-mode hızı | 5,386723 H/s |

## Kullanılan matematik
- Her nonce biti için tek-bitte değişimin GF(2) farkı: F(n XOR 2^i) XOR F(n).
- İki nonce biti için ikinci GF(2) fark: F(n XOR 2^i XOR 2^j) XOR F(n XOR 2^i) XOR F(n XOR 2^j) XOR F(n).
- Üç nonce biti için üçüncü GF(2) fark: sekiz altkümenin sonuçlarının XOR birleşimi.
- Nonzero üçüncü fark, gözlenen hedef-bit işlevinin ikinci dereceden veya daha düşük bir GF(2) polinomuyla tam açıklanamayacağını ispatlar.
- Bu bir hesaplama kestirmesi veya nonce tahmin algoritması değildir. GF(2) testi daha karmaşık cebirsel ve algoritmik ilişkilerin olmadığını kanıtlamaz.

## Kaynaklar
- Çalışan kaynak: https://github.com/byhicc-sudo/test/blob/nexis-rx-lab24-nonce-jacobian-20261102/nexis_rx_hist100/lab24_nonce_gf2_derivative.cpp
- Başarılı CI: https://github.com/byhicc-sudo/test/actions/runs/41365520387
- 561 adayın tam sonuçlarını içeren CSV artifact: https://github.com/byhicc-sudo/test/actions/runs/41365520387/artifacts/13107500402

## Net sonraki adım
LAB25, kazanan hash değerini tahmin eden tekli/ikili polinomlar yerine, ara VM hesaplamasında tam sonuç korunarak ertelenebilecek ya da ortadan kaldırılabilecek matematiksel bağımlılıklar aramalıdır. Her iddia tam hash doğruluğu ve işlem maliyetiyle test edilmelidir.
