# PDF Birleştirme Uygulaması

Bu proje, Python ile hazırlanmış masaüstü bir PDF birleştirme aracıdır.

## Özellikler

İki farklı mod sunar:

1. **İmzalanmış PDF'leri Birleştir**
   - `İmza sayfası` olarak bir PDF seçilir.
   - `Rapor` olarak ikinci bir PDF seçilir.
   - Rapor PDF'in **1. sayfası silinir**.
   - İmza PDF + raporun kalan sayfaları birleştirilir.

2. **PDF'leri Birleştir**
   - Birden fazla PDF seçilir.
   - Liste sırası değiştirilebilir (yukarı/aşağı).
   - Seçilen sıra ile tek dosya halinde birleştirilir.

## Çözünürlük Notu

Uygulama, PDF sayfalarını rasterize etmez (resme çevirmez); sayfalar doğrudan PDF nesneleri olarak taşınır.
Bu yüzden normal kullanımda çözünürlük kaybı oluşmaz.

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install pypdf
```

## Çalıştırma

```bash
python main.py
```

## Kullanım Akışı

- Uygulama açıldığında modu seçin.
- İlgili PDF dosyalarını seçin.
- `Birleştir ve Kaydet` ile çıktı dosyasını kaydedin.
