// Extend Tailwind with school palettes, glass, and font families
tailwind.config = {
    darkMode: 'class',
    theme: {
        extend: {
            fontFamily: {
                heading: ['Open Sans', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Inter', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
                body: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
            },
            colors: {
                // University of Virginia (UVA)
                hoo: {
                    blue: '#232D4B', // primary
                    orange: '#E57200',
                },
                // Virginia Tech (VT)
                hokie: {
                    maroon: '#861F41',
                    orange: '#E87722',
                },
                glass: {
                    1: 'rgba(255,255,255,0.08)',
                    2: 'rgba(255,255,255,0.12)',
                },
            },
            boxShadow: {
                glass: '0 1px 0 rgba(255,255,255,.12) inset, 0 10px 30px rgba(0,0,0,.35)',
            },
            backdropBlur: {
                xs: '2px',
            },
        },
    },
};
