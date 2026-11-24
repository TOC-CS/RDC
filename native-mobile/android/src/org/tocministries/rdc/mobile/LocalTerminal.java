package org.tocministries.rdc.mobile;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CodingErrorAction;
import java.nio.ByteBuffer;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.regex.Pattern;

/** Fixed command interpreter. No shell, process launch, network or external storage. */
public final class LocalTerminal {
    private static final int MAX=4096;
    private static final Pattern NAME=Pattern.compile("[A-Za-z0-9][A-Za-z0-9_.-]{0,63}");
    private final Path root;
    public LocalTerminal(Path root) { this.root=root.toAbsolutePath().normalize(); }
    public static final class Result {
        public final int exitCode;
        public final String output;
        public final double elapsedMs;
        public final String runId, commandDigest;
        Result(int code,String output,double ms,String id,String digest) {
            exitCode=code;this.output=output;elapsedMs=ms;runId=id;commandDigest=digest;
        }
        public String receipt() {
            return String.format(Locale.ROOT,"RDC terminal result | device-local | run=%s | command=%s | exit=%d | %.2f ms%n%s",runId,commandDigest,exitCode,elapsedMs,output);
        }
    }
    private static String hash(byte[] bytes) {
        try {
            byte[] digest=MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder s=new StringBuilder(64);
            for(byte b:digest) s.append(String.format(Locale.ROOT,"%02x",b&255));
            return s.toString();
        } catch(Exception e) { throw new IllegalStateException("Hash unavailable"); }
    }
    private static void require(boolean ok) { if(!ok)throw new IllegalArgumentException(); }
    private void prepare() throws Exception {
        if(!Files.exists(root,LinkOption.NOFOLLOW_LINKS))Files.createDirectory(root);
        require(Files.isDirectory(root,LinkOption.NOFOLLOW_LINKS));
    }
    private Path resolve(String name,boolean existing) {
        String[] parts=name.split("/",-1);require(parts.length>=1&&parts.length<=4);
        Path p=root;
        for(int i=0;i<parts.length;i++) {
            require(NAME.matcher(parts[i]).matches());
            p=p.resolve(parts[i]);
            if(i<parts.length-1)require(Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS));
        }
        if(existing)require(Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)||Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS));
        return p;
    }
    private static byte[] read(Path p) throws Exception {
        require(Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)&&Files.size(p)<=MAX);
        byte[] bytes=new byte[MAX+1];int n=0;
        try(InputStream in=Files.newInputStream(p,LinkOption.NOFOLLOW_LINKS)) {
            while(n<bytes.length) { int count=in.read(bytes,n,bytes.length-n);if(count<0)break;n+=count; }
        }
        require(n<=MAX);return Arrays.copyOf(bytes,n);
    }
    private static String list(Path p) throws Exception {
        require(Files.isDirectory(p,LinkOption.NOFOLLOW_LINKS));
        List<String> names=new ArrayList<>();int count=0;
        try(DirectoryStream<Path> stream=Files.newDirectoryStream(p)) {
            for(Path file:stream) { require(++count<=256);String name=file.getFileName().toString();if(NAME.matcher(name).matches())names.add(name); }
        }
        Collections.sort(names);String out=String.join("\n",names);
        require(out.getBytes(StandardCharsets.UTF_8).length<=MAX);return out;
    }
    public synchronized Result execute(String input) {
        long start=System.nanoTime();String runId=UUID.randomUUID().toString();String digest=hash(input==null?new byte[0]:input.getBytes(StandardCharsets.UTF_8));
        int code=1;String out="Command refused or unavailable. Use help; files must be inside /workspace. Existing files are preserved.";
        try {
            require(input!=null&&!input.isEmpty()&&input.getBytes(StandardCharsets.UTF_8).length<=MAX&&input.codePoints().noneMatch(Character::isISOControl));
            String[] a=input.trim().split(" +",3);require(a.length>0);prepare();
            String value;
            switch(a[0]) {
                case "help": require(a.length==1);value="pwd | ls [folder] | mkdir folder | write file text | cat file | sha256 file | echo text";break;
                case "pwd": require(a.length==1);value="/workspace";break;
                case "echo": value=a.length==1?"":a[1]+(a.length==3?" "+a[2]:"");break;
                case "ls": require(a.length<=2);value=list(a.length==1?root:resolve(a[1],true));break;
                case "mkdir": require(a.length==2);Files.createDirectory(resolve(a[1],false));value="Directory created";break;
                case "write": require(a.length==3);Files.write(resolve(a[1],false),a[2].getBytes(StandardCharsets.UTF_8),StandardOpenOption.CREATE_NEW,StandardOpenOption.WRITE);value="File created";break;
                case "cat":
                case "sha256":
                    require(a.length==2);byte[] data=read(resolve(a[1],true));
                    if(a[0].equals("sha256"))value=hash(data);
                    else {
                        String raw=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(data)).toString();
                        StringBuilder clean=new StringBuilder();raw.codePoints().filter(c->!Character.isISOControl(c)||c==10||c==9).forEach(clean::appendCodePoint);
                        value=clean.toString();
                    }
                    break;
                default:throw new IllegalArgumentException();
            }
            code=0;out=value;
        } catch(Exception ignored) {}
        return new Result(code,out,(System.nanoTime()-start)/1e6,runId,digest);
    }
}
