(function($) {

    // screen size
    function screenSize(elem) {
        var elHeight = $(window).height();
        $(elem).css('min-height', elHeight);
    }

    // absolute center
    function linkPosition() {
        var elem = $('[data-role="link"]');
        var elLeft = -elem.width()/2;
        var elTop = -elem.height()/2;
        elem.css({
            'position': 'absolute',
            'top': '55%',
            'left': '50%',
            // 'margin-top': elTop,
            'margin-left': elLeft
        });
    }

    function titleAbs() {
        var elem = $('[data-role="title"]');
        var elLeft = -elem.width()/2;
        var elTop = -elem.height()/2;
        elem.css({
            'position': 'absolute',
            'top': '35%',
            'left': '50%',
            'margin-top': elTop,
            'margin-left': elLeft
        });
    }

    // document ready
    $(window).on('load', function() {
        screenSize('[data-role="screen"]');
        titleAbs();
        linkPosition()
    });

    // all initial on window resize
    $(window).on('resize', function() {
        screenSize('[data-role="screen"]');
        titleAbs();
        linkPosition()
    });


})(jQuery);
