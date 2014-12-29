module.exports = function(grunt) {

    grunt.initConfig({

        sass: {
            dist: {
                options: {
                    style: 'expanded',
                    compass: false
                },
                files: {
                    'assets/css/style.css': 'assets/sass/style.scss'
                }
            }
        },

        autoprefixer: {
            options: {
                browsers: ['last 10 version']
            },
            multiple_files: {
                expand: true,
                flatten: true,
                src: 'assets/css/*.css',
                dest: 'static/css/'
            }
        },

        cssmin: {
            combine: {
                files: {
                    'static/css/style.min.css': ['static/css/style.css']
                }
            }
        },

        concat: {
            dist: {
                src: [
                    'assets/js/libs/jquery.js',
                    'assets/js/scripts.js'
                ],
                dest: 'static/js/production.js',
            }
        },

        uglify: {
            build: {
                src: 'static/js/production.js',
                dest: 'static/js/production.min.js',
            }
        },

        imagemin: {
            dynamic: {
                files: [{
                    expand: true,
                    cwd: 'assets/images/',
                    src: ['**/*.{png,jpg,gif}'],
                    dest: 'static/images/'
                }]
            }
        },

        watch: {
            options: {
                livereload: true,
            },
            scripts: {
                files: ['assets/js/*.js'],
                tasks: ['concat'],
                options: {
                    spawn: false,
                }
            },
            css: {
                files: ['assets/sass/*.scss', 'assets/sass/*/*.scss'],
                tasks: ['sass', 'autoprefixer'],
                options: {
                    spawn: false,
                    livereload: false,
                }
            },
            autoprefixer: {
                files: 'assets/css/**',
                tasks: ['autoprefixer']
            },
            images: {
                files: ['assets/images/*.{png,jpg,gif}'],
                tasks: ['imagemin'],
            }
        },

        connect: {
            server: {
                post: 8000, 
                base: './'
            }
        }

    });

    require('load-grunt-tasks')(grunt);

    grunt.registerTask('build', ['concat', 'uglify', 'imagemin', 'sass', 'autoprefixer', 'cssmin']);
    grunt.registerTask('run', ['connect', 'concat', 'imagemin', 'sass', 'autoprefixer', 'watch']);
    grunt.registerTask('default', ['run'])

};
