package org.tocministries.rdc.mobile;
import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.view.WindowManager;
import android.widget.*;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONObject;

public final class MainActivity extends Activity {
    private EditText origin, secret;
    private TextView status;
    private Button check;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Object requestLock = new Object();
    private Future<?> active;
    private HttpsURLConnection connection;
    private int generation = 0;
    private boolean terminalBusy = false;
    private int terminalGeneration = 0;
    private EditText terminalInput;
    private TextView terminalOutput;
    private Button terminalRun, terminalBack;


    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        showStatus();
    }

    private void showStatus() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(24 * getResources().getDisplayMetrics().density);
        panel.setPadding(pad,pad,pad,pad);
        scroll.addView(panel);
        TextView heading = new TextView(this);
        heading.setText("RDC Mobile"); heading.setTextSize(28); panel.addView(heading);
        TextView intro = new TextView(this);
        intro.setText("Independent gateway companion\nCheck your host with a read-only status token. This app does not grant control of the phone.");
        intro.setPadding(0,pad/2,0,pad); panel.addView(intro);
        TextView originLabel = new TextView(this);
        originLabel.setText("Gateway HTTPS origin"); panel.addView(originLabel);
        origin = new EditText(this);
        origin.setSingleLine(true);
        origin.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        origin.setHint("https://your-rdc-host"); origin.setSaveEnabled(false);
        origin.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO);
        panel.addView(origin,new LinearLayout.LayoutParams(-1,-2));
        TextView tokenLabel = new TextView(this);
        tokenLabel.setText("Read-only mobile status token"); panel.addView(tokenLabel);
        secret = new EditText(this);
        secret.setSingleLine(true);
        secret.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        secret.setHint("Private status token"); secret.setSaveEnabled(false);
        secret.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO);
        panel.addView(secret,new LinearLayout.LayoutParams(-1,-2));
        check = new Button(this); check.setText("Check connection"); panel.addView(check);
        check.setOnClickListener(v -> request());
        Button clear = new Button(this); clear.setText("Clear session"); panel.addView(clear);
        clear.setOnClickListener(v -> cancel(true));
        status = new TextView(this); status.setText("Connection not checked.");
        status.setPadding(0,pad/2,0,pad/2);
        status.setAccessibilityLiveRegion(android.view.View.ACCESSIBILITY_LIVE_REGION_POLITE);
        panel.addView(status);
        Button local=new Button(this);local.setText("Local terminal");panel.addView(local);
        local.setOnClickListener(v->{cancel(true);showTerminal();});
        setContentView(scroll);
    }

    private void showTerminal() {
        ScrollView scroll=new ScrollView(this);
        LinearLayout panel=new LinearLayout(this);panel.setOrientation(LinearLayout.VERTICAL);
        int pad=(int)(24*getResources().getDisplayMetrics().density);
        panel.setPadding(pad,pad,pad,pad);scroll.addView(panel);
        TextView heading=new TextView(this);heading.setText("RDC device-local terminal");heading.setTextSize(24);panel.addView(heading);
        TextView intro=new TextView(this);intro.setText("Commands run on this Android device in RDC's private workspace. No unrestricted system shell or remote SSH.");panel.addView(intro);
        terminalInput=new EditText(this);terminalInput.setHint("RDC local command");
        terminalInput.setSingleLine(true);terminalInput.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        terminalInput.setSaveEnabled(false);terminalInput.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO);panel.addView(terminalInput);
        terminalRun=new Button(this);terminalRun.setText("Run local command");panel.addView(terminalRun);
        terminalOutput=new TextView(this);terminalOutput.setText("Device-local sandbox. Type help.");terminalOutput.setTextIsSelectable(true);panel.addView(terminalOutput);
        Button clear=new Button(this);clear.setText("Clear output");panel.addView(clear);
        clear.setOnClickListener(v->{if(!terminalBusy){terminalInput.setText("");terminalOutput.setText("Output cleared.");}});
        terminalBack=new Button(this);terminalBack.setText("Gateway status");panel.addView(terminalBack);
        terminalBack.setOnClickListener(v->{if(!terminalBusy){terminalGeneration++;terminalInput.setText("");terminalOutput.setText("");terminalInput=null;terminalOutput=null;showStatus();}});
        terminalRun.setOnClickListener(v->runLocal());
        setContentView(scroll);
    }
    private void runLocal() {
        if(terminalBusy||terminalInput==null)return;
        final String command=terminalInput.getText().toString();if(command.isEmpty())return;
        terminalInput.setText("");terminalBusy=true;terminalRun.setEnabled(false);terminalBack.setEnabled(false);
        terminalOutput.setText("Running on this device…");
        final int id=++terminalGeneration;
        executor.execute(()->{
            String receipt=new LocalTerminal(getFilesDir().toPath().resolve("RDCWorkspace")).execute(command).receipt();
            runOnUiThread(()->{
                terminalBusy=false;
                if(terminalInput==null||isDestroyed())return;
                terminalRun.setEnabled(true);terminalBack.setEnabled(true);
                if(id==terminalGeneration)terminalOutput.setText(receipt);
            });
        });
    }

    private void request() {
        if (!check.isEnabled()) return;
        final URI uri;
        final String bearer;
        String raw = secret.getText().toString();
        secret.setText("");
        try {
            uri = GatewayContract.statusUri(origin.getText().toString());
            bearer = GatewayContract.token(raw);
        } catch (IllegalArgumentException e) {
            status.setText("Enter a trusted HTTPS gateway origin and a valid read-only token.");
            return;
        }
        final int id;
        synchronized (requestLock) { id = ++generation; }
        check.setEnabled(false); status.setText("Checking your gateway…");
        active = executor.submit(() -> {
            String result = "Connection unavailable. Check your gateway and certificate.";
            HttpsURLConnection current = null;
            try {
                current = (HttpsURLConnection)uri.toURL().openConnection();
                synchronized (requestLock) {
                    if (id != generation) return;
                    connection = current;
                }
                current.setInstanceFollowRedirects(false);
                current.setUseCaches(false);
                current.setConnectTimeout(10000);
                current.setReadTimeout(10000);
                current.setRequestMethod("POST");
                current.setRequestProperty("Authorization","Bearer "+bearer);
                current.setRequestProperty("Accept","application/json");
                current.setDoOutput(true);
                current.setFixedLengthStreamingMode(0);
                current.getOutputStream().close();
                int code = current.getResponseCode();
                if (code == 401) {
                    result = "Status disabled or token invalid.";
                } else if (code == 200) {
                    try (InputStream in=current.getInputStream(); ByteArrayOutputStream out=new ByteArrayOutputStream()) {
                        byte[] chunk=new byte[1024]; int n;
                        while ((n=in.read(chunk))!=-1) {
                            if (out.size()+n>8192) throw new IllegalArgumentException();
                            out.write(chunk,0,n);
                        }
                        JSONObject json=new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));
                        Object ok=json.opt("ok"), online=json.opt("online"), pending=json.opt("pending_operations");
                        if (!Boolean.TRUE.equals(ok) || !(online instanceof Boolean)
                                || !(pending instanceof Integer || pending instanceof Long)) throw new IllegalArgumentException();
                        long count=((Number)pending).longValue();
                        if (count<0 || count>9007199254740991L) throw new IllegalArgumentException();
                        result=((Boolean)online ? "Paired host connected" : "Paired host offline")
                                +" · "+count+" active operations.";
                    }
                }
            } catch (Exception ignored) {
                // Do not expose exception, URL, token or response data.
            } finally {
                if (current!=null) current.disconnect();
                synchronized (requestLock) { if (connection==current) connection=null; }
            }
            final String message=result;
            runOnUiThread(() -> {
                synchronized (requestLock) { if(id!=generation) return; }
                status.setText(message); check.setEnabled(true); active=null;
            });
        });
    }

    private void cancel(boolean clearOrigin) {
        HttpsURLConnection old;
        synchronized (requestLock) { generation++; old=connection; connection=null; }
        if (active!=null) { active.cancel(true); active=null; }
        if (old!=null) new Thread(old::disconnect,"rdc-connection-close").start();
        if (secret!=null) secret.setText("");
        if (clearOrigin && origin!=null) origin.setText("");
        if (status!=null) status.setText("Connection not checked.");
        if (check!=null) check.setEnabled(true);
    }
    @Override protected void onPause() {
        cancel(false);terminalGeneration++;
        if(terminalInput!=null){terminalInput.setText("");terminalOutput.setText("Output cleared.");}
        super.onPause();
    }
    @Override protected void onDestroy() { cancel(true); executor.shutdownNow(); super.onDestroy(); }
}
