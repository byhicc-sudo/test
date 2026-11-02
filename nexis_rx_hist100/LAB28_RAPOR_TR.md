# NEXİS-RX LAB28 — Matematiksel statik komut sadeleştirmesi

## Amaç ve yöntem
Gerçek bir Monero job'unun RandomX sanal makine programı derlendiği anda, önceden tam hash hesaplamadan **kesin matematiksel özdeşliklerle** bazı bytecode komutlarının devre dışı bırakılması. Belirli bir komut çifti için dallanmanın çiftin ikinci elemanına doğrudan atlayabilmesi kontrol edilir; bu durumda çift kaldırılmaz.

Güvenli sınanan kurallar: aynı register üzerinde iki negatif alma; aynı register/sabit kaynağı kullanan birbirini götüren XOR; saat yönünde ve ters yönde bit döndürme; iki swap; iki floating-point bit swap; iki floating-point bit XOR ölçekleme. Öncesindeki yuvarlama modu ayarı, bir sonraki yuvarlama ayarı arada başka floating-point işlemi veya CBRANCH olmadan geliyorsa atlanır. Floating-point FADD/FSUB gibi yuvarlama kaynaklı eşdeğer olmayan işlemler kaldırılmaz.

## Laboratuvar kanıtları
Resmî RandomX'in sabit C++ kaynak kodu kullanıldı: `102f8acf90a7649ada410de5499a7ec62e49e1da`. Aynı gerçek tarihsel seed, Monero blok yüksekliği 3300100'den başlayan 100 farklı gerçek blok kullanıldı.

### İlk deney — tek blok
- 16 nonce × 4 tur = **64/64 tam 256 bitlik doğru RandomX hash**.
- 2 optimize tur = 256 program; 18 cebirsel olarak iptal edilen komut çifti, 36 değiştirilmiş komut, 0 güvenle silinen CFROUND.
- İlk denemede `STANDARD_MODE_HPS=7.448190`, `STATIC_SIMPLIFIED_MODE_HPS=7.466846`; oran `1.002505`. Bu küçük tek koşu farkı, hızlanma olarak kanıtlanmadı.

### Geniş doğrulama — farklı 100 blok
- **100/100** tarihsel gerçek Monero kazanan nonce'unun tam PoW hash'i yeniden doğrulandı.
- Aynı 100 job'un nonce+1 değerleri için de orijinal ile yeni yöntem birebir karşılaştırıldı.
- **200/200** ayrı iş girdisinde optimize motorun 256-bit hash'i resmî tam RandomX ile eşleşti.
- 200 hash × 8 program = **1.600** optimize edilmiş programda **94** güvenle iptal edilebilen komut çifti ve **10** kullanılmadan üzerine yazılan CFROUND bulundu.
- Bu 1.600 programdaki değiştirilen toplam komut = `94*2+10=198`, toplam statik komut sayısı = `1600*256=409600`; yalnızca **%0,04834**.
- 64-hash çapraz kıyaslamada resmî/interpreted motorun aynı kütüphane içi kontrol hızı: **15,271684 H/s**.
- Sadeleştirilmiş motor hızı: **15,064299 H/s**.
- Ölçülen oran: **0,986420×**; yaklaşık **%1,358 yavaşlama**.
- İki farklı runner zamanı arasında fark oluştuğundan ilk +%0,25 ve ikinci -%1,36 ölçümü istikrarlı bir hızlanmaya kanıt değildir. Kontrol ve modlar aynı koşuda kıyaslandı; iki koşu karşılaştırılıp hız artışı iddia edilmez.

## Sınırlar ve karar
- Komutları `NOP` yapma, VM dispatch maliyetini tamamen kaldırmaz; statik kesintisiz etki çok azdır.
- Derleme sırasında bilinen özdeşlikler **gerçek matematiksel sadeleştirmedir**, ancak matematiksel nonce bulma kestirmesi veya kesin erken elemeye dönüşmedi.
- Doğrulanmış 200/200 eşleşme tüm olası job'lar için formal kanıt değildir; kuralların cebirsel doğruluğu ve branch-girişi kontrolü ile desteklenen saha doğrulamasıdır.
- Genel madencilik hız artışı, 5000× avantaj veya yeni gerçek ağ bloğu **elde edilmedi**.
- Sonraki çalışma, aynı tek-komut cebirsel sadeleştirmeleri tekrar etmek yerine, nonce daha başta girildiğinde tam RandomX'i çalıştırmadan gerçek hedefi sınamaya yetecek bir zorunlu durum kısıtı bulunabilir mi sorusuna odaklanmalıdır; bu koşul bulunamıyorsa hipotez kapatılır.

## Çalışma bağlantıları
- Son doğrulanmış CI: https://github.com/byhicc-sudo/test/actions/runs/41384449980
- Son CSV/ham CI dosyaları: https://github.com/byhicc-sudo/test/actions/runs/41384449980/artifacts/13114309156
- C++ kaynak: https://github.com/byhicc-sudo/test/blob/nexis-rx-lab28-static-identities-20261102/nexis_rx_hist100/lab28_static_identities.cpp
- Instrumentasyon: https://github.com/byhicc-sudo/test/blob/nexis-rx-lab28-static-identities-20261102/nexis_rx_hist100/lab28_patch_official.py
