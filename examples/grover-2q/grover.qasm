// 2-qubit Grover search marking |11>. A single iteration is optimal for N=4,
// so an ideal run measures |11> with probability 1.
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
// uniform superposition
h q[0];
h q[1];
// oracle: phase-flip |11>
cz q[0], q[1];
// diffusion (inversion about the mean)
h q[0];
h q[1];
x q[0];
x q[1];
cz q[0], q[1];
x q[0];
x q[1];
h q[0];
h q[1];
measure q -> c;
