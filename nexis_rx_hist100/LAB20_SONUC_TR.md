# NEXİS-RX LAB20 — Gerçek RandomX nonce bulucu

## Kapsam
Resmî RandomX C++ v1.2.1 (commit `102f8acf90a7649ada410de5499a7ec62e49e1da`) ile eski bir Monero bloğunun gerçek 76 baytlık PoW girdisi kullanılır. Önce gerçek tarihsel kazanan nonce, *yalnız doğrulama amacıyla* ayrıca hesaplanır; ardından aday üreticinin girdisinden silinir.

## Aday üretimi
İşin nonce hariç girdisi ile RandomX seed'inden deterministik FNV durum değeri türetilir. Aday nonce:

`nonce(i) = (start + i * stride) mod 2^32`

Burada `stride` tektir. Bu nedenle tüm 2^32 nonce boyunca tekrar olmaz. Bu yöntem sıradan art arda nonce denemesinden daha yüksek başarı olasılığı **sağlamaz**; tekrar kontrolü ve paralel aralık bölüştürmesi için kullanılan bir tarama düzenidir.

## Kesin kazanç koşulu
`little_endian_uint256(RandomX(job,nonce)) * difficulty <= 2^256-1`

İşlem sonucu tam 256 bit üzerinden karşılaştırılır. RandomX hesaplanmadan kazanan nonce'u çıkartan matematiksel kestirme bulunmuş değildir.

## Gerçek ölçüm
- Kaynak blok: 3.300.100; ağ zorluğu: 367410898587.
- Kontrol: gerçek tarihsel hash ve ağ hedefi doğru.
- Tek bir gerçek PoW blob'unda 768 farklı nonce, resmî RandomX light mode C++ ile hesaplandı.
- 137.321 saniye; 5.59273 H/s.
- Hedef zorluğu 32: 26/768 geçerli.
- Hedef zorluğu 128: 8/768 geçerli.
- Hedef zorluğu 256: 3/768 geçerli.
- Bu deneyde gerçek tarihsel ağ zorluğunda yeni blok: 0/768.
- İlk 256-zorluk geçerli yeni nonce: `20448078`, sekizinci deneme (indeks 7).
- Hash: `b4ccfd492784220124e24772aec13032e47e427a33c907ba35c6efe71ebe0a00`
- Aday dizisi: `start=1207143931`, `stride=4125439317`.
- Giriş BLAKE2b ilk baytı 64'ten küçük değil diye 576/768 nonce reddedilseydi, 32-zorlukta geçerli **26 hash'ten 19'u yanlış reddedilecekti**. Bu filtrenin güvenilir olmadığı kanıtlanmıştır.

## Önemli sınırlamalar
1. Kod **gerçek PoW sonuçları hesaplayan deneysel arama çekirdeğidir**; canlı node'a bağlı otomatik solo madenci değildir.
2. Deneyde bulunan 256 zorluklu çözüm, **ağ bloğu** değildir; bunun blok ödülü yoktur. Zorluk 256 örneği yalnızca kontrol edilebilir düşük eşikli test içindir.
3. Tek sabit job'un nonce uzayı sınırlıdır; gerektiğinde geçerli yeni blok şablonları alınmalıdır.
4. Bu deney **RandomX'i daha az çalıştıran bir kriptanalitik kısa yol kanıtlamamıştır**.

## Dosyalar
- `nexis_rx_hist100/lab20_solo_finder.cpp`
- `.github/workflows/nexis-rx-lab20-finder.yml`
- Başarılı koşu: https://github.com/byhicc-sudo/test/actions/runs/41360423939
- Tam aday CSV arşivi: https://github.com/byhicc-sudo/test/actions/runs/41360423939/artifacts/13105110861
