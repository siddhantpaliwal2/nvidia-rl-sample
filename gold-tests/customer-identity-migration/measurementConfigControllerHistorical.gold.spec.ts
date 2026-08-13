import { Test, TestingModule } from '@nestjs/testing';
import { forwardRef } from '@nestjs/common';
import { InfluxModule } from '../influx/influx.module';
import { SchedulerModule } from '../scheduler/scheduler.module';
import { MeasurementConfigController } from './measurement-config.controller';
import { MeasurementConfigService } from './measurement-config.service';
import { PrivateAPIDimensionsModule } from '../dimensions/dimensions.module';

describe('MeasurementConfigController', () => {
    let controller: MeasurementConfigController;

    // const client = createClient();
    // afterAll(async () => {
    //     await client.quit();
    // });
    beforeEach(async () => {
        const module: TestingModule = await Test.createTestingModule({
            controllers: [MeasurementConfigController],
            providers: [MeasurementConfigService],
            imports: [InfluxModule, forwardRef(() => PrivateAPIDimensionsModule)],
        }).compile();

        controller = module.get<MeasurementConfigController>(MeasurementConfigController);
    });

    it('should be defined', () => {
        expect(controller).toBeDefined();
    });
});
