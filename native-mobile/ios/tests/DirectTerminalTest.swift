import Foundation
import CryptoKit
import Darwin

@main struct DirectTerminalTest {
 static func main() throws {
  let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
  try FileManager.default.createDirectory(at: root, withIntermediateDirectories: false)
  defer { try? FileManager.default.removeItem(at: root) }
  let docs = root.appendingPathComponent("Documents")
  try FileManager.default.createDirectory(at: docs, withIntermediateDirectories: false)
  let workspace = root.appendingPathComponent("workspace")
  let transport = DirectTerminalMailbox(documents: docs, workspace: workspace)
  var checks=0
  func check(_ label: String, _ condition: @autoclosure () -> Bool) {
   precondition(condition(), label); checks += 1; print("PASS \(label)")
  }
  func digest(_ s:String)->String { SHA256.hash(data:Data(s.utf8)).map{String(format:"%02x",$0)}.joined() }
  func request(_ id: String, _ command:String, _ override:String?=nil, extra:Bool=false) throws {
   var data:[String:Any]=["schema":1,"request_id":id,"command":command,"command_sha256":override ?? digest(command)]
   if extra {data["unexpected"]=true}
   try JSONSerialization.data(withJSONObject:data).write(to:docs.appendingPathComponent("rdc-request-"+id+".json"))
  }
  func result(_ id:String)throws->[String:Any] {
   try JSONSerialization.jsonObject(with:Data(contentsOf:docs.appendingPathComponent("rdc-result-"+id+".json"))) as! [String:Any]
  }
  func id()->String { UUID().uuidString.lowercased() }
  if CommandLine.arguments.dropFirst().first == "--publication-sync-red" {
   let u=id();try request(u,"echo sync-fixture")
   let io=DirectTerminalMailbox.ReceiptIO(write:{Darwin.write($0,$1,$2)},sync:{_ in errno=EIO;return -1})
   let outcome=DirectTerminalMailbox(documents:docs,workspace:workspace,receiptIO:io).process(u)
   if outcome == .completed { print("EXPECTED_RED_RECEIPT_SYNC_FAILURE_IGNORED");exit(1) }
   print("PUBLICATION_SYNC_FAILURE_REPORTED");exit(outcome == .outcomeUnknown ? 0 : 2)
  }
  let a=id();try request(a,"echo fixture")
  check("exact command executes",transport.process(a) == .completed)
  let receipt=try result(a)
  check("verified result fields",receipt["request_id"] as? String==a && receipt["command_sha256"] as? String==digest("echo fixture") && receipt["exit_code"] as? Int==0 && receipt["output"] as? String=="fixture")
  let b=id();try request(b,"write example.txt first")
  check("create-only command",transport.process(b) == .completed)
  let initial=try result(b)
  try request(b,"write example.txt second")
  check("changed request cannot replay claimed UUID",transport.process(b) == .alreadyClaimed)
  let after=try result(b)
  check("receipt unchanged",initial["run_id"] as? String==after["run_id"] as? String)
  let content=try String(contentsOf:workspace.appendingPathComponent("example.txt"),encoding:.utf8)
  check("original file retained",content=="first")
  let c=id();try request(c,"echo bad",String(repeating:"0",count:64))
  check("digest mismatch refused",transport.process(c) == .refused)
  let d=id();try request(d,"echo bad",extra:true)
  check("extra fields refused",transport.process(d) == .refused)
  let e=id();try request(e,"echo "+String(repeating:"x",count:4001))
  check("oversize refused",transport.process(e) == .refused)
  let f=id();try request(f,"echo bad\nsecond")
  check("control characters refused",transport.process(f) == .refused)
  check("invalid UUID refused",transport.process("../outside") == .refused)
  let g=id();try request(g,"write should-not-exist.txt test")
  try Data("claimed".utf8).write(to:docs.appendingPathComponent("rdc-claim-"+g))
  check("interrupted claim never re-executes",transport.process(g) == .alreadyClaimed)
  check("interrupted command no new file",!FileManager.default.fileExists(atPath:workspace.appendingPathComponent("should-not-exist.txt").path))
  let h=id();try request(h,"echo fixture")
  let outside=root.appendingPathComponent("outside");try Data("unchanged".utf8).write(to:outside)
  try FileManager.default.createSymbolicLink(at:docs.appendingPathComponent("rdc-result-"+h+".json"),withDestinationURL:outside)
  check("preexisting result refused before execution",transport.process(h) == .refused)
  let unchanged=try String(contentsOf:outside,encoding:.utf8)
  check("external target untouched",unchanged=="unchanged")
  let k=id()
  try FileManager.default.createSymbolicLink(at:docs.appendingPathComponent("rdc-request-"+k+".json"),withDestinationURL:outside)
  check("symlink request refused",transport.process(k) == .refused)
  // Faults affect receipt publication only; the durable no-replay claim remains real.
  var writeCalls=0,syncCalls=0
  let shortIO=DirectTerminalMailbox.ReceiptIO(write:{fd,p,n in
   writeCalls += 1
   if writeCalls==1 {errno=EINTR;return -1}
   return Darwin.write(fd,p,writeCalls==2 ? min(n,7) : n)
  },sync:{fd in
   syncCalls += 1
   if syncCalls==1 {errno=EINTR;return -1}
   return Darwin.fsync(fd)
  })
  let short=id();try request(short,"echo short-write")
  check("short write and interruption complete",DirectTerminalMailbox(documents:docs,workspace:workspace,receiptIO:shortIO).process(short) == .completed)
  let shortResult=try result(short)
  check("short write receipt exact",shortResult["output"] as? String=="short-write" && shortResult["request_id"] as? String==short)
  check("file and directory sync verified",writeCalls==3 && syncCalls==3)
  let resultAttributes=try FileManager.default.attributesOfItem(atPath:docs.appendingPathComponent("rdc-result-"+short+".json").path)
  check("receipt owner-only permissions",(resultAttributes[.posixPermissions] as? NSNumber)?.intValue == 0o600)
  var zeroCalls=0
  let zeroIO=DirectTerminalMailbox.ReceiptIO(write:{fd,p,n in zeroCalls += 1;return zeroCalls==1 ? Darwin.write(fd,p,min(n,5)) : 0},sync:{Darwin.fsync($0)})
  let zero=id();try request(zero,"write durability-zero.txt original")
  let zeroTransport=DirectTerminalMailbox(documents:docs,workspace:workspace,receiptIO:zeroIO)
  check("zero progress reports unknown",zeroTransport.process(zero) == .outcomeUnknown)
  try request(zero,"write durability-zero.txt replacement")
  check("partial receipt cannot replay",zeroTransport.process(zero) == .alreadyClaimed)
  let zeroContent=try String(contentsOf:workspace.appendingPathComponent("durability-zero.txt"),encoding:.utf8)
  check("partial receipt retains original effect",zeroContent=="original" && zeroCalls==2)
  let fileIO=DirectTerminalMailbox.ReceiptIO(write:{Darwin.write($0,$1,$2)},sync:{_ in errno=EIO;return -1})
  let file=id();try request(file,"echo file-sync")
  let fileTransport=DirectTerminalMailbox(documents:docs,workspace:workspace,receiptIO:fileIO)
  check("file sync failure reports unknown",fileTransport.process(file) == .outcomeUnknown)
  check("file sync failure cannot replay",fileTransport.process(file) == .alreadyClaimed)
  var directorySyncs=0
  let directoryIO=DirectTerminalMailbox.ReceiptIO(write:{Darwin.write($0,$1,$2)},sync:{fd in directorySyncs += 1;if directorySyncs==2 {errno=EIO;return -1};return Darwin.fsync(fd)})
  let directory=id();try request(directory,"echo directory-sync")
  let directoryTransport=DirectTerminalMailbox(documents:docs,workspace:workspace,receiptIO:directoryIO)
  check("directory sync failure reports unknown",directoryTransport.process(directory) == .outcomeUnknown)
  check("directory sync failure cannot replay",directoryTransport.process(directory) == .alreadyClaimed && directorySyncs==2)
  var interruptions=0
  let interruptedIO=DirectTerminalMailbox.ReceiptIO(write:{_,_,_ in interruptions += 1;errno=EINTR;return -1},sync:{Darwin.fsync($0)})
  let interrupted=id();try request(interrupted,"echo interrupted-write")
  check("write interruption budget is finite",DirectTerminalMailbox(documents:docs,workspace:workspace,receiptIO:interruptedIO).process(interrupted) == .outcomeUnknown && interruptions==64)
  var syncInterruptions=0
  let interruptedSyncIO=DirectTerminalMailbox.ReceiptIO(write:{Darwin.write($0,$1,$2)},sync:{_ in syncInterruptions += 1;errno=EINTR;return -1})
  let interruptedSync=id();try request(interruptedSync,"echo interrupted-sync")
  check("sync interruption budget is finite",DirectTerminalMailbox(documents:docs,workspace:workspace,receiptIO:interruptedSyncIO).process(interruptedSync) == .outcomeUnknown && syncInterruptions==8)
  print("DIRECT_TERMINAL_CASES=\(checks)")
 }
}
