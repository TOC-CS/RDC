package org.tocministries.rdc.mobile;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.Comparator;
public final class LocalTerminalTest {
    static int count=0;
    static void check(String name,boolean ok) { if(!ok)throw new AssertionError(name);count++;System.out.println("PASS "+name); }
    public static void main(String[] args)throws Exception {
        Path tmp=Files.createTempDirectory("rdc-local-terminal-");
        try {
            Path root=tmp.resolve("workspace");LocalTerminal t=new LocalTerminal(root);
            check("virtual cwd",t.execute("pwd").output.equals("/workspace"));
            check("literal echo",t.execute("echo a; b").output.equals("a; b"));
            check("mkdir",t.execute("mkdir sub").exitCode==0);
            check("write",t.execute("write sub/test.txt abc").exitCode==0);
            check("read",t.execute("cat sub/test.txt").output.equals("abc"));
            check("hash",t.execute("sha256 sub/test.txt").output.equals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));
            check("no overwrite",t.execute("write sub/test.txt replacement").exitCode!=0);
            check("traversal",t.execute("cat ../outside").exitCode!=0);
            Path outside=tmp.resolve("outside");Files.write(outside,"outside".getBytes(StandardCharsets.UTF_8));Files.createSymbolicLink(root.resolve("link"),outside);
            check("symlink refused",t.execute("cat link").exitCode!=0);
            check("unsupported shell",t.execute("sh -c id").exitCode!=0);
            check("bounded input",t.execute("echo "+new String(new char[4096]).replace('\0','x')).exitCode!=0);
            check("listing",t.execute("ls sub").output.equals("test.txt"));
            System.out.println("LOCAL_TERMINAL_CASES="+count);
        }finally{try(java.util.stream.Stream<Path> paths=Files.walk(tmp)){paths.sorted(Comparator.reverseOrder()).forEach(p->{try{Files.delete(p);}catch(Exception e){throw new RuntimeException(e);}});}}
    }
}
