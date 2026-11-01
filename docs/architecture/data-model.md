# Veri Modeli ve Değişmez Kurallar (Adım 1)

## Varlıklar

- **Kullanıcı:** kimlik, ad, rol (roller: yönetici, teklif uzmanı, salt okunur). Rol değişimleri denetim kaydına yazılır.
- **Ürün:** kod, adlar, eşanlamlılar, özellikler (ad/değer listesi), birim. Katalogun ana kaydıdır.
- **FiyatSürümü:** ürün → fiyat, para birimi, yürürlük aralığı, durum (taslak / yürürlükte / arşiv). Aynı ürünün tek yürürlükteki sürümü olabilir.
- **ŞartSürümü:** şart kümesi (teslim, ödeme, geçerlilik vb.), yürürlük aralığı, durum (taslak / yürürlükte / arşiv). Tek yürürlükteki sürüm kuralı geçerlidir.
- **Talep:** müşteri, başlık, durum (açık / teklifte / kapalı).
- **TalepSürümü:** talep → sürüm no, kaynak dosya işareti, çıkarılmış metin, sayfa/bölüm yapısı. Önceki sürüme bağlantı taşır.
- **Gereksinim:** sürüm → ürün tipi, özellikler, miktar, birim, toleranslar, **kaynak işaretçisi (zorunlu: dosya + sayfa/bölüm + alıntı)**.
- **EşleşmeÖnerisi:** gereksinim → ürün, skor, gerekçe, kaynak işaretçileri (zorunlu), durum (bekliyor / onaylandı / reddedildi / düzeltildi), inceleyen, zaman.
- **EksikBilgi:** gereksinim/sürüm → alan, soru metni, zorunluluk, durum (açık / yanıtlandı / vazgeçildi).
- **SürümFarkı:** eski sürüm → yeni sürüm, değişiklik kalemleri (alan, eski değer, yeni değer).
- **AlternatifÖneri:** gereksinim → ürün, kriter karşılaştırması, gerekçe, durum (bekliyor / onaylandı / reddedildi).
- **Teklif:** talep → durum (taslak / incelemede / onaylandı / dışa aktarıldı), hazırlayan, onaylayan, zamanlar.
- **TeklifKalemi:** teklif → ürün, miktar, **üretildiği andaki FiyatSürümü kimliği (sabitlenir)**, tutar. Teklif ayrıca **ŞartSürümü kimliğini** taşır.
- **SaklananDosya:** özgün ad, içerik adresi, bütünlük karması. Yazıldıktan sonra değiştirilemez.
- **DenetimKaydı:** zaman, aktör, işlem, nesne, önce/sonra özeti. Yalnızca eklenir; güncellenemez, silinemez.

## Durum Makineleri

- Teklif: taslak → incelemede → onaylandı → dışa aktarıldı. Geri dönüşler (incelemede → taslak) denetim kaydıyla olur; onaylandı → taslak geçişi yoktur, yeni taslak sürüm açılır.
- EşleşmeÖnerisi ve AlternatifÖneri: bekliyor → onaylandı / reddedildi; onaylanan öneride sonradan değişiklik yerine "düzeltildi" izi bırakan yeni karar gerekir.

## Değişmezlerin Denetim Noktaları

1. **Kaynaksız öneri gösterilmez.** Gereksinim ve EşleşmeÖnerisi kayıtlarında kaynak işaretçisi boş bırakılamaz (yazma anında zorunlu); okuma katmanı işaretsiz kaydı listelemez. Doğrulama: işaretsiz kayıt yazma denemesi reddedilir.
2. **Onaysız dışa aktarma yok.** Belge çıktısı yalnızca durumu "onaylandı" olan tekliften üretilir; dışa aktarma işlemi onaylayan kimliği ve zamanı denetim kaydına yazar, durumu "dışa aktarıldı" yapar. Doğrulama: onaysız tekliften çıktı denemesi engellenir.
3. **Yalnızca onaylı fiyat/şart.** Teklif kalemi yazılırken ürünün yürürlükteki FiyatSürümü çözülür ve kimliği kaleme sabitlenir; şartlar için yürürlükteki ŞartSürümü teklife sabitlenir. Yürürlükte sürümü olmayan ürün teklif kalemine giremez. Doğrulama: eski teklif, fiyat değişiminden sonra ilk üretildiği sürüm değerlerini göstermeye devam eder.

## Bütünlük Notları

- Sürüm ve denetim kayıtları yalnızca eklenir; düzeltme yeni kayıtla yapılır.
- Dosya deposundaki içerik ile veritabanındaki işaretçilerin eşleşmesi düzenli doğrulama işiyle denetlenir.
- Skor eşikleri ve zorunlu alan listeleri yapılandırmada durur, kodda sabitlenmez.

## Adım 1 Kabul Kontrolü

- [ ] Kaynak işaretçisiz gereksinim/öneri yazma denemesi reddedilir.
- [ ] Onaysız tekliften belge çıktısı denemesi engellenir.
- [ ] Fiyat/şart değişiminden sonra eski teklif eski sürüm değerlerini korur.
