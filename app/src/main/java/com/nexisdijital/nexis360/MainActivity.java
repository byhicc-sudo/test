package com.nexisdijital.nexis360;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.location.Location;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.*;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int LOCATION_REQUEST = 360;
    private Spinner serviceSpinner, requestSpinner;
    private EditText nameInput, phoneInput, detailInput;
    private TextView locationText;
    private WebView mapView;
    private double latitude = Double.NaN, longitude = Double.NaN;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
    }

    private TextView label(String text, int size, boolean bold) {
        TextView v = new TextView(this);
        v.setText(text); v.setTextSize(size); v.setTextColor(Color.rgb(25, 38, 55));
        if (bold) v.setTypeface(null, android.graphics.Typeface.BOLD);
        v.setPadding(0, 14, 0, 8);
        return v;
    }

    private void buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(28, 30, 28, 38);
        root.setBackgroundColor(Color.rgb(245, 247, 250));
        scroll.addView(root);

        TextView brand = label("NEXIS360", 30, true);
        brand.setTextColor(Color.rgb(0, 92, 160));
        root.addView(brand);
        TextView title = label("Mahallem Teknik Hizmet Talebi", 20, true);
        root.addView(title);
        TextView intro = label("Elektrik, kamera, internet ve otomatik kapı ihtiyaçlarınızı konumuyla birlikte NEXİS Dijital'e iletin.", 15, false);
        intro.setTextColor(Color.DKGRAY);
        root.addView(intro);

        root.addView(label("Hizmet", 16, true));
        serviceSpinner = new Spinner(this);
        String[] services = {"Elektrik", "Kamera Sistemleri", "İnternet / Network", "Bahçe Kapısı", "Otomatik Kapı", "Diafon / Görüntülü Diafon", "Alarm / Güvenlik", "Diğer Teknik Hizmet"};
        serviceSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, services));
        root.addView(serviceSpinner);

        root.addView(label("Talep türü", 16, true));
        requestSpinner = new Spinner(this);
        String[] requestTypes = {"Arıza / Servis Talebi", "Yeni Kurulum", "Keşif ve Fiyat Teklifi", "Bakım / Kontrol"};
        requestSpinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, requestTypes));
        root.addView(requestSpinner);

        root.addView(label("Sorunu veya ihtiyacınızı anlatın", 16, true));
        detailInput = new EditText(this);
        detailInput.setHint("Örnek: Apartman giriş kamerası görüntü vermiyor...");
        detailInput.setMinLines(4); detailInput.setGravity(android.view.Gravity.TOP);
        root.addView(detailInput, new LinearLayout.LayoutParams(-1, -2));

        root.addView(label("Konum", 16, true));
        LinearLayout locationButtons = new LinearLayout(this);
        locationButtons.setOrientation(LinearLayout.HORIZONTAL);
        Button currentLocation = new Button(this); currentLocation.setText("Mevcut Konumum");
        Button openMap = new Button(this); openMap.setText("Haritadan Seç");
        locationButtons.addView(currentLocation, new LinearLayout.LayoutParams(0, -2, 1));
        locationButtons.addView(openMap, new LinearLayout.LayoutParams(0, -2, 1));
        root.addView(locationButtons);
        locationText = label("Henüz konum seçilmedi.", 14, false);
        root.addView(locationText);

        mapView = new WebView(this);
        mapView.setVisibility(View.GONE);
        mapView.getSettings().setJavaScriptEnabled(true);
        mapView.getSettings().setDomStorageEnabled(true);
        mapView.setWebViewClient(new WebViewClient());
        mapView.addJavascriptInterface(new MapBridge(), "Android");
        root.addView(mapView, new LinearLayout.LayoutParams(-1, 760));

        root.addView(label("Ad Soyad", 16, true));
        nameInput = new EditText(this); nameInput.setHint("Adınız ve soyadınız"); root.addView(nameInput);
        root.addView(label("Telefon", 16, true));
        phoneInput = new EditText(this); phoneInput.setHint("05xx xxx xx xx"); phoneInput.setInputType(android.text.InputType.TYPE_CLASS_PHONE); root.addView(phoneInput);

        CheckBox consent = new CheckBox(this);
        consent.setText("İletişim ve konum bilgilerimin talebimin değerlendirilmesi amacıyla kullanılmasını kabul ediyorum.");
        consent.setPadding(0, 16, 0, 16);
        root.addView(consent);

        Button send = new Button(this);
        send.setText("WHATSAPP İLE TALEBİ GÖNDER");
        send.setTextSize(16); send.setTextColor(Color.WHITE);
        send.setBackgroundColor(Color.rgb(0, 140, 95));
        root.addView(send, new LinearLayout.LayoutParams(-1, 145));

        TextView footer = label("NEXİS Dijital • 0542 267 82 64", 14, true);
        footer.setGravity(android.view.Gravity.CENTER); root.addView(footer);

        currentLocation.setOnClickListener(v -> requestCurrentLocation());
        openMap.setOnClickListener(v -> showMap());
        send.setOnClickListener(v -> {
            if (!consent.isChecked()) { toast("Devam etmek için onay kutusunu işaretleyin."); return; }
            sendWhatsApp();
        });
        setContentView(scroll);
    }

    private void requestCurrentLocation() {
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION}, LOCATION_REQUEST);
            return;
        }
        LocationManager lm = (LocationManager) getSystemService(LOCATION_SERVICE);
        if (!lm.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
            toast("Telefon konumunu açmanız gerekiyor.");
            startActivity(new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS));
            return;
        }
        try {
            lm.requestSingleUpdate(LocationManager.GPS_PROVIDER, location -> setLocation(location.getLatitude(), location.getLongitude()), null);
            toast("Konum belirleniyor...");
        } catch (SecurityException e) { toast("Konum izni alınamadı."); }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == LOCATION_REQUEST && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) requestCurrentLocation();
        else toast("Konum izni verilmedi. Haritadan seçim yapabilirsiniz.");
    }

    private void showMap() {
        mapView.setVisibility(View.VISIBLE);
        double lat = Double.isNaN(latitude) ? 40.7654 : latitude;
        double lon = Double.isNaN(longitude) ? 29.9408 : longitude;
        String html = "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/><style>html,body,#map{height:100%;margin:0} .note{position:absolute;z-index:999;background:white;padding:8px;left:8px;top:8px;border-radius:8px;font-family:sans-serif}</style></head><body><div class='note'>Haritada talep noktasına dokunun</div><div id='map'></div><script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script><script>var map=L.map('map').setView(["+lat+","+lon+"],16);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'OpenStreetMap'}).addTo(map);var m=L.marker(["+lat+","+lon+"]).addTo(map);map.on('click',function(e){m.setLatLng(e.latlng);Android.setLocation(e.latlng.lat,e.latlng.lng);});</script></body></html>";
        mapView.loadDataWithBaseURL("https://nexisdijital.com", html, "text/html", "UTF-8", null);
    }

    private void setLocation(double lat, double lon) {
        latitude = lat; longitude = lon;
        runOnUiThread(() -> locationText.setText(String.format(Locale.US, "Seçilen konum: %.6f, %.6f", lat, lon)));
    }

    public class MapBridge { @JavascriptInterface public void setLocation(double lat, double lon) { MainActivity.this.setLocation(lat, lon); } }

    private void sendWhatsApp() {
        String name = nameInput.getText().toString().trim();
        String phone = phoneInput.getText().toString().trim();
        String detail = detailInput.getText().toString().trim();
        if (name.length() < 3 || phone.length() < 10 || detail.length() < 5) { toast("Ad soyad, telefon ve açıklama alanlarını eksiksiz doldurun."); return; }
        if (Double.isNaN(latitude)) { toast("Lütfen mevcut konumunuzu alın veya haritadan bir nokta seçin."); return; }
        String no = "N360-" + new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
        String map = "https://maps.google.com/?q=" + latitude + "," + longitude;
        String msg = "*NEXIS360 MAHALLEM YENİ TALEP*\n\n" +
                "*Talep No:* " + no + "\n" +
                "*Hizmet:* " + serviceSpinner.getSelectedItem() + "\n" +
                "*Talep Türü:* " + requestSpinner.getSelectedItem() + "\n" +
                "*Açıklama:* " + detail + "\n\n" +
                "*Müşteri:* " + name + "\n" +
                "*Telefon:* " + phone + "\n" +
                "*Konum:* " + map;
        try {
            String encoded = URLEncoder.encode(msg, StandardCharsets.UTF_8.toString());
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/905422678264?text=" + encoded)));
        } catch (Exception e) { toast("WhatsApp açılamadı. Lütfen tekrar deneyin."); }
    }

    private void toast(String text) { Toast.makeText(this, text, Toast.LENGTH_LONG).show(); }
}
