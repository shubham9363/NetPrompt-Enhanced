Valid P4 code for a simple firewall with ACL rules:

```
module PACKAGE_NAME (PACKAGE_INPUT);

interface INTERFACE_INPUT;
  // input packet data from network
endinterface: INTERFACE_INPUT;

(* synthesize *)
module mkFIREWALL (INTERFACE_OUTPUT);

  // Create a table to store ACL rules
  // Rule names will be generated based on the first few bytes of each packet
  Reg#(Bit#(8)) rg_table <- mkRegU;

  // Initialize the table with default ACL rules
  for (Integer I = 0; I < 256; i=i+1) begin
    // Rule name is generated as the first four bytes of the packet's IP address and UDP port number
    AXI4_Slave_AWLEN #(32, 32) addr <- mkAXI4_WSTAG_AWLEN(i, 0);
    AXI4_Slave_ARLEN #(32, 32) len   <- mkAXI4_WSTAG_ARLEN(i, 0);
    AXI4_Slave_RREADY_B <- mkAXI4_SLAVE_RREADY_B(i, 1);
    Reg #(Bit#(32)) rg_rule <- mkRegU;

    // Define an 'entry' function for each ACL rule
    (*synthesize*)
    rule entry (rg_table[i/8] != 0 and rg_table[i/8+1:i/8] != 0);
      // Extract the 'entry' rule from the table at index i/8, with ACL rules defined in the lower 32 bits of each packet's IP address and UDP port number.
      AXI4_Slave_AWLEN #(32, 32) aw_rule <- mkAXI4_WSTAG_AWLEN(i/8+1, i/8);
      AXI4_Slave_ARLEN #(32, 32) ar_rule <- mkAXI4_WSTAG_ARLEN(i/8+1, i/8);
      AXI4_Slave_RDATA #(32) data <- mkAXI4_WSTAG_RDATA(i/8+1, 0); // Clear RDATA if there's no rule matching the current index
      AXI4_Slave_AWREADY_B <- mkAXI4_WSTAG_AWREADY_B(i, aw_rule.len + data.len);
      AXI4_Slave_ARREADY_B <- mkAXI4_WSTAG_ARREADY_B(i, ar_rule.len + data.len);
    endrule
  endrule

  // Define a 'process' function for each packet with an 'entry' rule defined
  (*synthesize*)
  rule process (rg_table[16] != 0 and rg_table[17:16] != 0);
    AXI4_Slave_AWLEN #(32, 32) aw_rule <- mkAXI4_WSTAG_AWLEN(rg_table[16], 0); // Clear AWLEN if there's no rule matching the current index
    AXI4_Slave_ARLEN #(32, 32) ar_rule <- mkAXI4_WSTAG_ARLEN(rg_table[16], 0);
    AXI4_Slave_RDATA #(32) data <- mkAXI4_WSTAG_RDATA(rg_table[16], aw_rule.len + ar_rule.len + data.len); // Clear RDATA if there's no rule matching the current index
    AXI4_Slave_AWREADY_B <- mkAXI4_WSTAG_AWREADY_B(rg_table[16], aw_rule.len + ar_rule.len + data.len);
    AXI4_Slave_ARREADY_B <- mkAXI4_WSTAG_ARREADY_B(rg_table[16], aw_rule.len + ar_rule.len + data.len);
  endrule

  // Define a 'process' function for each packet without an 'entry' rule defined
  (*synthesize*)
  rule process (rg_table[32] != 0 and rg_table[33:32] != 0);
    AXI4_Slave_AWLEN #(32, 32) aw_rule <- mkAXI4_WSTAG_AWLEN(rg_table[32], 0); // Clear AWLEN if there's no rule matching the current index
    AXI4_Slave_ARLEN #(32, 32) ar_rule <- mkAXI4_WSTAG_ARLEN(rg_table[32], 0);
    AXI4_Slave_RDATA #(32) data <- mkAXI4_WSTAG_RDATA(rg_table[32], aw_rule.len + ar_rule.len + data.len); // Clear RDATA if there's no rule matching the current index
    AXI4_Slave_AWREADY_B <- mkAXI4_WSTAG_AWREADY_B(rg_table[32], aw_rule.len + ar_rule.len + data.len);
    AXI4_Slave_ARREADY_B <- mkAXI4_WSTAG_ARREADY_B(rg_table[32], aw_rule.len + ar_rule.len + data.len);
  endrule

  // Define a 'process' function for each packet with no 'entry' rule defined
  (*synthesize*)
  rule process (rg_table[64] != 0 and rg_table[65:64] != 0);
    AXI4_Slave_AWLEN #(32, 32) aw_rule <- mkAXI4_WSTAG_AWLEN(rg_table[64], 0); // Clear AWLEN if there's no rule matching the current index
    AXI4_Slave_ARLEN #(32, 32) ar_rule <- mkAXI4_WSTAG_ARLEN(rg_table[64], 0);
    AXI4_Slave_RDATA #(32) data <- mkAXI4_WSTAG_RDATA(rg_table[64], aw_rule.len + ar_rule.len + data.len); // Clear RDATA if there's no rule matching the current index
    AXI4_Slave_AWREADY_B <- mkAXI4_WSTAG_AWREADY_B(rg_table[64], aw_rule.len + ar_rule.len + data.len);
    AXI4_Slave_ARREADY_B <- mkAXI4_WSTAG_ARREADY_B(rg_table[64], aw_rule.len + ar_rule.len + data.len);
  endrule
endmodule