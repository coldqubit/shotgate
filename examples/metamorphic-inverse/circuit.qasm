// Metamorphic pattern: U followed by U^-1 (its exact inverse, gates reversed and negated)
// must return |000>, regardless of what U itself computes. U here stands in for an
// arbitrary circuit whose own correct output distribution may not be known in closed
// form; the assertion needs no `expected` about U, only the algebraic identity U.U^-1 = I.
OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];

// U: an arbitrary, moderately entangling circuit.
h q[0];
cx q[0], q[1];
rz(0.7) q[1];
cx q[1], q[2];
h q[2];

// U^-1: same gates, reverse order, each inverted (rz(-theta), self-inverse H/CX unchanged).
h q[2];
cx q[1], q[2];
rz(-0.7) q[1];
cx q[0], q[1];
h q[0];

measure q -> c;
