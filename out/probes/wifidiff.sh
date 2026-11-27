for f in reg icc genpd clk stats; do echo "=== $f (- wifi up  + wifi blocked)"; diff /tmp/snap-up/$f /tmp/snap-down/$f | grep '^[-+][^-+]' | cut -c1-170 | head -40; done
