'use strict';

/* jasmine specs for services */

describe('service', function() {

  beforeEach(module('playgroundApp.services'));


  describe('DoSerial', function() {

    it('should be chainable', inject(function(DoSerial) {
      var result = DoSerial.then(function() {});
      expect(result).toBe(DoSerial);
      result = DoSerial.tick(function() {});
      expect(result).toBe(DoSerial);
    }));


    it('should execute simple task', inject(function(DoSerial, $timeout) {
      var called = false;
      DoSerial.then(function() { called = true; });
      expect(called).toBe(false);
      flushDoSerial($timeout);
      expect(called).toBe(true);
    }));


    it('should execute tasks in order', inject(function(DoSerial, $timeout, $log) {
      DoSerial.then(function() { $log.log(1); });
      DoSerial.tick();
      DoSerial
      .then(function() { $log.log(2); })
      .then(function() { $log.log(3); })
      .tick()
      .then(function() { $log.log(4); })
      DoSerial.tick();
      flushDoSerial($timeout);
      expect($log.log.logs).toEqual([[1], [2], [3], [4]]);
    }));


    xit('should accept both promises and functions', inject(function(DoSerial) {
      // TODO
    }));


    // TODO: figure out how to test this functionality
    xit('should continue after exception', inject(function(DoSerial, $timeout, $log) {
      DoSerial
      .then(function() { $log.log(1); })
      .then(function() { throw 'banana peel'; })
      .then(function() { $log.log(2); })
      expect($log.assertEmpty());
      try {
        flushDoSerial($timeout);
      } catch(e) {
        $log.log('test caught:' + e);
      }
      expect($log.error.logs).toEqual([['DoSerial encountered']]);
      expect($log.log.logs).toEqual([[1], ['test caught: banana peel'], [2]]);
    }));

  });

});
