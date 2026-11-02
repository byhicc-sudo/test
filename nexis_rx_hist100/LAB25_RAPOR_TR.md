# NEXİS-RX LAB25 — Job sabitken nonce'lar arasında hesap paylaşımı

## Amaç
Aynı gerçek Monero job'unda farklı nonce'lar için üretilen RandomX programlarının ve 64-baytlık dataset satırlarının tam aynı olup olmadığını ölçmek. Yalnız resmî, tam 256-bit RandomX hash'iyle sonuçları doğrulamak; benzer opcode'ları aynı hesaplama sanmamak.

## Girdi ve koşullar
- Gerçek tarihsel Monero blok: 3300100
- Bilinen tarihsel nonce: 1079945234
- Aynı blok girdisi, nonce 1079945234...1079945249 arasında 16 tam hash
- Seed hash: ede5e439528eee8366e06971e881221d3ff12a0b76152e4c462ca0642dce732d
- Resmî RandomX kaynak kodu sabit commit: 102f8acf90a7649ada410de5499a7ec62e49e1da
- Light mode, 8 VM programı × 2048 VM iterasyonu. Her üretilen program 256 talimattan oluşur.
- Tek enstrümantasyon: light-mode datasetRead fonksiyonu adresini bir kayıt işlevine aktarır. Hesap algoritması, dataset öğeleri ve VM çıktıları değiştirilmedi.
- Tam resmî API ile el ile takip edilen 8-program zincirindeki hash'ler: 16/16 eşleşme.

## Gerçek sonuçlar
| Ölçüm | Değer |
|---|---:|
| Karşılaştırılan farklı nonce | 15 |
| Üretilen toplam program | 128 |
| Toplam üretilen talimat | 32768 |
| Aynı program aşamasında birebir aynı program | 0/120 |
| Aynı aşama ve konumda aynı 8-bayt talimat | 0/30720 |
| Aynı aşama ve konumda yalnız aynı opcode | 132/30720 |
| Aynı aşama ve konumda 64-bit entropy aynılığı | 0/1920 |
| Dataset okuma çağrısı | 262144 |
| Farklı dataset adresi | 261135 |
| İdeal sınırsız önbelleğin yakalayabileceği tekrarlar | 1009/262144 = %0,3849 |
| Kazananla aynı iterasyondaki dataset adresi | 0/245760 |
| 15 komşu nonce'da kazananın dataset adresleriyle toplam eşleşen benzersiz adresler | 133 |

## Yorum
Nonce'ların farklı ürettiği programlar arasında aynı konumda birebir tekrar eden talimat görülmedi. Dataset okumalarının %0,385'i daha önce kullanılan aynı 64-baytlık dataset öğesine yöneldi. Bu tekrarlar, **yalnız aynı item'ı ikinci kez hesaplamamaya yönelik** ideal sınırsız önbelleğin teorik fırsatı. Item üretimi tek başına bütün çalışma maliyetini oluştursa bile yalnız bu tekrarları sıfırlamanın en iyi olası oransal hızlanması yaklaşık %0,386'dır: 262144 / 261135 = 1,0038645×. Gerçek sistemde hash map aramaları ve bellek maliyeti olur; RandomX full mode önceden oluşturulmuş dataset kullandığından karşılaştırma konusu farklıdır.

Bu sınır farklı nonce'lar arasında yapılabilecek **her türlü** hesap paylaşımının imkânsız olduğunu kanıtlamaz. Yalnız resmî programın birebir aynı adres/komutunun doğrudan önbelleğe alınmasını bu 16 örnek için değerlendirir.

## Araştırma kararı
1. Aynı job'un komşu nonce'larında programın birebir aynı çıkacağı veya dataset okumalarının yaygın biçimde tekrarlayacağı varsayımını terk ediyoruz.
2. Tek bir nonce'un hesap zinciri içinde neden zorunlu olmayan işlemler doğabileceği veya olamayacağı, bit-bit canlı bağımlılık ve eşdeğerlik ispatıyla araştırılmalı.
3. Yeni bir yöntem ancak gerçek ağ hedefini değiştirmeden aynı 256-bit hash'i veriyor ve resmî motora karşı ölçülebilir hesap maliyeti azaltıyorsa kabul edilir.
4. 5000× hedefi kanıtlanmış değildir; 16-nonce gözlemiyle teorik bir RandomX çözümüne ulaşıldığı iddia edilmez.

## Kaynaklar
- Gerçek GitHub Actions deneyi: https://github.com/byhicc-sudo/test/actions/runs/41366309814
- Tam ölçümler CSV: https://github.com/byhicc-sudo/test/actions/runs/41366309814/artifacts/13106719959
- Çalışan C++: https://github.com/byhicc-sudo/test/blob/nexis-rx-lab25-reuse-trace-20261102/nexis_rx_hist100/lab25_job_reuse_trace.cpp
